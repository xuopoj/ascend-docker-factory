#!/usr/bin/env python3
import yaml
import subprocess
import sys
import argparse
import os
from pathlib import Path

def run_command(cmd):
    print(f"🔨 [EXEC] {cmd}")
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    ret = subprocess.call(cmd, shell=True, env=env)
    if ret != 0:
        print("❌ Build failed!")
        sys.exit(1)

def load_images_config():
    with open("dockerfile-compose.yaml", "r") as f:
        return yaml.safe_load(f)

def get_build_order(config, target=None):
    """Calculate build order based on dependencies"""
    images = config['images']
    
    if target and target not in images:
        print(f"❌ Image '{target}' not found in config")
        sys.exit(1)
    
    # If target specified, only build that image and its dependencies
    if target:
        to_build = set()
        def collect_deps(image_name):
            if image_name in to_build:
                return
            to_build.add(image_name)
            deps = images.get(image_name, {}).get('depends_on', [])
            for dep in deps:
                collect_deps(dep)
        collect_deps(target)
        images = {k: v for k, v in images.items() if k in to_build}
    
    # Simple topological sort
    built = set()
    order = []
    
    def can_build(image_name):
        deps = images.get(image_name, {}).get('depends_on', [])
        return all(dep in built for dep in deps)
    
    while len(built) < len(images):
        ready = [name for name in images if name not in built and can_build(name)]
        if not ready:
            print("❌ Circular dependency detected!")
            sys.exit(1)
        
        for image_name in ready:
            order.append(image_name)
            built.add(image_name)
    
    return order

def build_image(image_name, image_config):
    print(f"\n📦 Building {image_name}")
    
    build_config = image_config['build']
    dockerfile = build_config['dockerfile']
    context = build_config.get('context', '.')
    
    # Get the primary tag (first one in the list)
    primary_tag = image_config.get('tags', [f"temp_{image_name}"])[0]
    
    # Build directly with the final tag
    cmd_parts = [
        f"docker build",
        f"-f {dockerfile}",
        f"-t {primary_tag}",
    ]
    
    # Add build args
    if 'args' in build_config:
        for key, value in build_config['args'].items():
            cmd_parts.append(f"--build-arg {key}={value}")
    
    cmd_parts.append(context)
    cmd = " ".join(cmd_parts)
    
    run_command(cmd)
    
    # Add additional tags if there are more than one
    additional_tags = image_config.get('tags', [])[1:]
    for tag in additional_tags:
        run_command(f"docker tag {primary_tag} {tag}")

        
def generate_mermaid_graph(config):
    """Generate a Mermaid flowchart showing image dependencies"""
    images = config['images']
    
    print("```mermaid")
    print("flowchart TD")
    
    # Add all nodes
    for image_name in images:
        # Clean name for Mermaid (replace hyphens with underscores for node IDs)
        node_id = image_name.replace('-', '_')
        print(f"    {node_id}[{image_name}]")
    
    # Add dependencies (edges)
    for image_name, image_config in images.items():
        node_id = image_name.replace('-', '_')
        deps = image_config.get('depends_on', [])
        for dep in deps:
            dep_id = dep.replace('-', '_')
            print(f"    {dep_id} --> {node_id}")
    
    # Add styling for different types
    print("    %% Styling")
    print("    classDef baseImage fill:#e1f5fe")
    print("    classDef framework fill:#f3e5f5")
    print("    classDef application fill:#e8f5e8")
    
    # Classify images by type
    base_images = []
    framework_images = []
    app_images = []
    
    for image_name in images:
        node_id = image_name.replace('-', '_')
        if 'python' in image_name:
            base_images.append(node_id)
        elif any(fw in image_name for fw in ['pytorch', 'cann']):
            framework_images.append(node_id)
        else:
            app_images.append(node_id)
    
    if base_images:
        print(f"    class {','.join(base_images)} baseImage")
    if framework_images:
        print(f"    class {','.join(framework_images)} framework")
    if app_images:
        print(f"    class {','.join(app_images)} application")
    
    print("```")

def main():
    parser = argparse.ArgumentParser(description="Build Docker images using dockerfile-compose")
    parser.add_argument("--target", help="Build specific image and its dependencies")
    parser.add_argument("--list", action="store_true", help="List all available images")
    parser.add_argument("--graph", action="store_true", help="Generate Mermaid dependency graph")
    args = parser.parse_args()
    
    config = load_images_config()
    
    if args.list:
        print("Available images:")
        for name, conf in config['images'].items():
            tags = ", ".join(conf.get('tags', []))
            deps = conf.get('depends_on', [])
            deps_str = f" (depends on: {', '.join(deps)})" if deps else ""
            print(f"  {name}: {tags}{deps_str}")
        return
    
    if args.graph:
        generate_mermaid_graph(config)
        return
    
    build_order = get_build_order(config, args.target)
    
    print(f"🚀 Build order: {' -> '.join(build_order)}")
    
    for image_name in build_order:
        build_image(image_name, config['images'][image_name])
    
    print("✅ All builds completed!")

if __name__ == "__main__":
    main()
