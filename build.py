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

def load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

load_env()

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

def write_catalog_entry(image_name, image_config, all_images, modelscope_url=None):
    catalog_dir = Path("catalog")
    catalog_dir.mkdir(exist_ok=True)

    build_config = image_config.get('build', {})
    dockerfile_path = build_config.get('dockerfile', '')
    args = build_config.get('args', {})

    # Read dockerfile content and substitute ARG defaults with actual build args
    dockerfile_content = ""
    if dockerfile_path and Path(dockerfile_path).exists():
        dockerfile_content = Path(dockerfile_path).read_text(encoding="utf-8")
        for key, value in args.items():
            dockerfile_content = re.sub(
                rf'^(ARG {key}=).*$',
                rf'\g<1>{value}',
                dockerfile_content,
                flags=re.MULTILINE,
            )

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
        "modelscopeUrl": modelscope_url,
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

def delete_image(image_config):
    for tag in image_config.get('tags', []):
        run_command(f"docker rmi {tag}")

def save_image(image_name, image_config):
    """Save image as compressed tarball, return path."""
    tag = image_config.get('tags', [])[0]
    tarball = Path(f"{image_name}.tar.gz")
    print(f"💾 Saving {tag} → {tarball}")
    # Pull fresh to avoid corrupt local cache (e.g. after disk issues)
    run_command(f"docker pull {tag}")
    ret = subprocess.call(f"docker save {tag} | gzip > {tarball}", shell=True)
    if ret != 0:
        print("❌ Save failed!")
        sys.exit(1)
    size_mb = tarball.stat().st_size / 1024 / 1024
    print(f"   Size: {size_mb:.1f} MB")
    return tarball

def modelscope_upload(image_name, image_config, tarball_path):
    """Upload tarball to ModelScope and update images.jsonl. Returns download URL."""
    token = os.environ.get("MODELSCOPE_TOKEN")
    if not token:
        print("❌ MODELSCOPE_TOKEN not set")
        sys.exit(1)

    from modelscope.hub.api import HubApi
    api = HubApi()
    api.login(token)

    repo_id = "xuopoj/service-delivery-hub"
    # e.g. vllm-ascend/vllm-ascend-v0.16.0rc1.tar.gz
    folder = image_name.rsplit("-", 1)[0] if image_name[-1].isdigit() else image_name
    # use image_name prefix up to version part as folder
    # e.g. "vllm-ascend-v0.16.0rc1" -> folder "vllm-ascend"
    parts = image_name.split("-")
    folder = "-".join(p for p in parts if not p.startswith("v") or not p[1:2].isdigit())
    path_in_repo = f"{folder}/{tarball_path.name}"

    print(f"⬆️  Uploading to ModelScope {repo_id}/{path_in_repo}")
    api.upload_file(
        path_or_fileobj=str(tarball_path),
        path_in_repo=path_in_repo,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Add {image_name}",
    )

    # Build direct download URL
    download_url = f"https://modelscope.cn/datasets/{repo_id}/resolve/master/{path_in_repo}"
    print(f"   URL: {download_url}")

    # Update images.jsonl
    _update_images_jsonl(api, repo_id, image_name, image_config, path_in_repo, download_url)

    return download_url

def _update_images_jsonl(api, repo_id, image_name, image_config, path_in_repo, download_url):
    """Fetch images.jsonl, upsert current image entry, re-upload."""
    import urllib.request
    jsonl_path = "images.jsonl"
    lines = {}

    # Try to fetch existing file
    try:
        url = api.get_dataset_file_url(
            file_name=jsonl_path,
            dataset_name="service-delivery-hub",
            namespace="xuopoj",
        )
        with urllib.request.urlopen(url) as resp:
            content = resp.read().decode("utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line:
                entry = json.loads(line)
                lines[entry["id"]] = entry
    except Exception:
        pass  # File doesn't exist yet, start fresh

    # Build catalog entry for this image
    build_args = image_config.get("build", {}).get("args", {})
    lines[image_name] = {
        "id": image_name,
        "tag": image_config.get("tags", [""])[0],
        "purpose": image_config.get("purpose"),
        "tarball": path_in_repo,
        "modelscopeUrl": download_url,
        "pushedAt": datetime.now(timezone.utc).isoformat(),
        "args": build_args,
    }

    new_content = "\n".join(json.dumps(e) for e in lines.values()) + "\n"
    api.upload_file(
        path_or_fileobj=new_content.encode("utf-8"),
        path_in_repo=jsonl_path,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Update images.jsonl for {image_name}",
    )
    print(f"📋 images.jsonl updated on ModelScope")

    _update_modelscope_readme(api, repo_id, lines)

def _update_modelscope_readme(api, repo_id, all_entries):
    """Regenerate README.md on ModelScope with current image table."""
    readme_template = (Path(__file__).parent / "modelscope-readme.md").read_text(encoding="utf-8")

    # Group entries by image family (e.g. "vllm-ascend")
    families = {}
    for entry in all_entries.values():
        parts = entry["id"].split("-")
        # family = everything before the version segment (starts with 'v' + digit)
        family_parts = []
        for p in parts:
            if p.startswith("v") and p[1:2].isdigit():
                break
            family_parts.append(p)
        family = "-".join(family_parts) if family_parts else entry["id"]
        families.setdefault(family, []).append(entry)

    # Build image table sections
    table_sections = []
    for family, entries in sorted(families.items()):
        rows = []
        for e in sorted(entries, key=lambda x: x["id"]):
            version = e["id"][len(family)+1:]  # strip "vllm-ascend-"
            tag = e["tag"]
            url = e.get("modelscopeUrl", "")
            tarball_name = url.split("/")[-1] if url else f"{e['id']}.tar.gz"
            rows.append(f"| {version} | `{tag}` | [{tarball_name}]({url}) |")
        table = "\n".join([
            f"### {family}",
            "",
            "| 版本 | quay.io 标签 | 下载 |",
            "|------|-------------|------|",
        ] + rows)
        table_sections.append(table)

    # Replace the table block in readme (between ## 可用镜像 and the next ---)
    new_section = "## 可用镜像 / Available Images\n\n" + "\n\n".join(table_sections) + "\n\n---"
    updated = re.sub(
        r"## 可用镜像 / Available Images.*?---",
        new_section,
        readme_template,
        flags=re.DOTALL,
    )

    api.upload_file(
        path_or_fileobj=updated.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Update README image table",
    )
    print(f"📄 README.md updated on ModelScope")

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
    parser.add_argument("--delete", action="store_true", help="Delete local image after pushing (saves disk space)")
    parser.add_argument("--save", action="store_true", help="Save image as tar.gz and upload to ModelScope")
    parser.add_argument("--rc", metavar="TAG", help="Push as release candidate with suffix (e.g. --rc rc1)")
    parser.add_argument("--no-build", action="store_true", help="Skip build step (use existing local image)")
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
        if not args.no_build:
            build_image(image_name, config['images'][image_name], config['images'])
        if args.push or args.rc:
            push_image(image_name, config['images'][image_name], rc=args.rc)
        if not args.rc and (args.push or args.save or args.no_build):
            modelscope_url = None
            if args.save:
                tarball = save_image(image_name, config['images'][image_name])
                modelscope_url = modelscope_upload(image_name, config['images'][image_name], tarball)
                tarball.unlink()
                print(f"🗑️  Deleted local tarball {tarball}")
            write_catalog_entry(image_name, config['images'][image_name], config['images'], modelscope_url)
        if args.delete:
            delete_image(config['images'][image_name])

    print("✅ All builds completed!")

if __name__ == "__main__":
    main()
