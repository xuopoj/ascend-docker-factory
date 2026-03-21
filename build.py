#!/usr/bin/env python3
import yaml
import subprocess
import sys
import argparse
import os
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import re

def run_command(cmd):
    print(f"🔨 [EXEC] {cmd}")
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    ret = subprocess.call(cmd, shell=True, env=env)
    if ret != 0:
        print("❌ Build failed!")
        sys.exit(1)

def expand_matrix(config):
    """Expand matrix entries into individual image configs."""
    images = config['images']
    expanded = {}
    for name, image_config in images.items():
        matrix = image_config.pop('matrix', None)
        if not matrix:
            expanded[name] = image_config
            continue
        # Currently supports a single matrix variable
        var, values = next(iter(matrix.items()))
        for value in values:
            instance_name = f"{name}-{value}"
            instance = copy.deepcopy(image_config)
            # Inject matrix var as build arg
            instance.setdefault('build', {}).setdefault('args', {})[var] = value
            # Substitute {VAR} in tags
            instance['tags'] = [t.replace(f"{{{var}}}", value) for t in instance.get('tags', [])]
            expanded[instance_name] = instance
    config['images'] = expanded
    return config

def load_images_config():
    with open("dockerfile-compose.yaml", "r") as f:
        config = yaml.safe_load(f)
    return expand_matrix(config)

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

def resolve_base_image(image_name, image_config, all_images):
    """Resolve BASE_IMAGE from depends_on if not explicitly specified."""
    build_config = image_config.get('build', {})
    args = build_config.get('args', {})

    # If BASE_IMAGE is explicitly set, use it
    if 'BASE_IMAGE' in args:
        return args['BASE_IMAGE']

    # If there's exactly one dependency, use its first tag as BASE_IMAGE
    deps = image_config.get('depends_on', [])
    if len(deps) == 1:
        dep_name = deps[0]
        dep_config = all_images.get(dep_name, {})
        dep_tags = dep_config.get('tags', [])
        if dep_tags:
            return dep_tags[0]

    return None

def rc_tag(tag, rc):
    """Convert a tag to its RC variant: repo/image:ver → repo/image:ver-rc1"""
    if ":" in tag:
        repo, version = tag.rsplit(":", 1)
        return f"{repo}:{version}-{rc}"
    return f"{tag}-{rc}"

def write_catalog_entry(image_name, image_config, all_images):
    catalog_dir = Path("catalog")
    catalog_dir.mkdir(exist_ok=True)

    build_config = image_config.get('build', {})
    dockerfile_path = build_config.get('dockerfile', '')
    args = build_config.get('args', {})

    # Read dockerfile content
    dockerfile_content = ""
    if dockerfile_path and Path(dockerfile_path).exists():
        dockerfile_content = Path(dockerfile_path).read_text(encoding="utf-8")

    # Resolve base image id from depends_on
    deps = image_config.get('depends_on', [])
    base_image_id = deps[0] if deps else None

    entry = {
        "id": image_name,
        "name": image_name.split('-')[0],
        "tag": image_config.get('tags', [''])[0],
        "dockerfile": dockerfile_content,
        "dockerfilePath": dockerfile_path,
        "baseImageId": base_image_id,
        "args": args,
        "purpose": image_config.get('purpose'),
        "chip": args.get('CHIP_TYPE'),
        "cannVersion": args.get('CANN_VERSION'),
        "installType": "online" if "8.5" in dockerfile_path else "offline",
        "pushedAt": datetime.now(timezone.utc).isoformat(),
    }

    out = catalog_dir / f"{image_name}.json"
    out.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    print(f"📋 Catalog entry written: {out}")

def push_image(image_name, image_config, rc=None):
    for tag in image_config.get('tags', []):
        push_tag = rc_tag(tag, rc) if rc else tag
        if rc:
            run_command(f"docker tag {tag} {push_tag}")
        run_command(f"docker push {push_tag}")

def build_image(image_name, image_config, all_images):
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

    # Resolve BASE_IMAGE from depends_on if not explicitly set
    resolved_base = resolve_base_image(image_name, image_config, all_images)
    if resolved_base:
        cmd_parts.append(f"--build-arg BASE_IMAGE={resolved_base}")

    # Add build args (skip BASE_IMAGE if we already resolved it)
    if 'args' in build_config:
        for key, value in build_config['args'].items():
            if key == 'BASE_IMAGE' and resolved_base:
                continue
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
    parser.add_argument("--push", action="store_true", help="Push images to registry after building")
    parser.add_argument("--rc", metavar="TAG", help="Push as release candidate with suffix (e.g. --rc rc1)")
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
        build_image(image_name, config['images'][image_name], config['images'])
        if args.push or args.rc:
            push_image(image_name, config['images'][image_name], rc=args.rc)
            if not args.rc:
                write_catalog_entry(image_name, config['images'][image_name], config['images'])

    print("✅ All builds completed!")

if __name__ == "__main__":
    main()
