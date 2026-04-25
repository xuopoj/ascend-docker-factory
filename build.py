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

        # Matrix can be:
        #   - dict: {VAR: [val1, val2]} — single variable, values are scalars
        #   - list: [{VAR1: v1, VAR2: v2, _tag_suffix: s, _depends_on: d}, ...] — multi-variable
        if isinstance(matrix, dict):
            var, values = next(iter(matrix.items()))
            rows = [{var: value, '_tag_suffix': value} for value in values]
        else:
            rows = matrix  # list of dicts

        for row in rows:
            row = dict(row)
            suffix = row.pop('_tag_suffix', None)
            depends_on_override = row.pop('_depends_on', None)
            experimental_override = row.pop('_experimental', None)

            # Derive suffix from first non-special value if not given
            if suffix is None:
                suffix = next(iter(row.values()))

            instance_name = f"{name}-{suffix}"
            instance = copy.deepcopy(image_config)

            # Build substitution map: matrix vars + _tag_suffix
            sub = dict(row)
            sub['_tag_suffix'] = suffix

            # Inject matrix vars (excluding _tag_suffix) as build args
            for var, value in row.items():
                instance.setdefault('build', {}).setdefault('args', {})[var] = value

            # Substitute {VAR} and {_tag_suffix} in tags
            for var, value in sub.items():
                instance['tags'] = [t.replace(f"{{{var}}}", value) for t in instance.get('tags', [])]

            # Override depends_on if specified
            if depends_on_override:
                instance['depends_on'] = [depends_on_override] if isinstance(depends_on_override, str) else depends_on_override

            # Override experimental if specified
            if experimental_override is not None:
                instance['experimental'] = experimental_override

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

def write_catalog_entry(image_name, image_config, all_images, modelscope_url=None, sha256=None, quay_digest=None):
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
        "tier": image_config.get('tier'),
        "purpose": image_config.get('purpose'),
        "appType": image_config.get('app_type'),
        "appName": image_config.get('app_name'),
        "description": image_config.get('description'),
        "chip": args.get('CHIP_TYPE'),
        "cannVersion": args.get('CANN_VERSION'),
        "experimental": image_config.get('experimental', False),
        "pushedAt": datetime.now(timezone.utc).isoformat(),
        "modelscopeUrl": modelscope_url,
        "sha256": sha256,
        "quayDigest": quay_digest,
    }

    out = catalog_dir / f"{image_name}.json"
    out.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    print(f"📋 Catalog entry written: {out}")

def push_image(image_name, image_config, rc=None):
    """Push image tags; return the manifest digest of the primary tag (or None)."""
    digest = None
    for i, tag in enumerate(image_config.get('tags', [])):
        push_tag = rc_tag(tag, rc) if rc else tag
        if rc:
            run_command(f"docker tag {tag} {push_tag}")
        if i == 0 and not rc:
            # Capture output to extract manifest digest
            print(f"🔨 [EXEC] docker push {push_tag}")
            env = os.environ.copy()
            env["DOCKER_BUILDKIT"] = "1"
            result = subprocess.run(f"docker push {push_tag}", shell=True, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(result.stdout, end="")
            if result.returncode != 0:
                print("❌ Build failed!")
                sys.exit(1)
            for line in result.stdout.splitlines():
                if "digest:" in line and "sha256:" in line:
                    m = re.search(r'sha256:[a-f0-9]+', line)
                    if m:
                        digest = m.group(0)
                        print(f"   Quay digest: {digest}")
                        break
        else:
            run_command(f"docker push {push_tag}")
    return digest

def delete_image(image_config):
    for tag in image_config.get('tags', []):
        run_command(f"docker rmi {tag}")

def sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_tarball(tarball: Path, tag: str):
    """docker load the tarball, verify it succeeds, then remove the loaded image."""
    print(f"🔍 Verifying {tarball} ...")
    ret = subprocess.call(f"docker load < {tarball}", shell=True)
    if ret != 0:
        print("❌ docker load failed — tarball is corrupt!")
        sys.exit(1)
    subprocess.call(f"docker rmi {tag}", shell=True)
    print(f"   Verified OK")


def save_image(image_name, image_config, no_pull=False):
    """Save image as compressed tarball, verify it, calc sha256, return (path, sha256)."""
    tag = image_config.get('tags', [])[0]
    tarball = Path(f"{image_name}.tar.gz")
    print(f"💾 Saving {tag} → {tarball}")
    if not no_pull:
        run_command(f"docker pull {tag}")
    ret = subprocess.call(f"docker save {tag} | gzip > {tarball}", shell=True)
    if ret != 0:
        print("❌ Save failed!")
        sys.exit(1)
    size_mb = tarball.stat().st_size / 1024 / 1024
    print(f"   Size: {size_mb:.1f} MB")
    verify_tarball(tarball, tag)
    checksum = sha256_file(tarball)
    print(f"   SHA256: {checksum}")
    return tarball, checksum

def modelscope_upload(image_name, image_config, tarball_path, sha256=None, quay_digest=None):
    """Upload tarball to ModelScope and update images.jsonl. Returns download URL."""
    token = os.environ.get("MODELSCOPE_TOKEN")
    if not token:
        print("❌ MODELSCOPE_TOKEN not set")
        sys.exit(1)

    from modelscope.hub.api import HubApi
    api = HubApi()
    api.login(token)

    repo_id = "xuopoj/service-delivery-hub"
    # Use image family name as folder: "python-3.10" -> "python", "vllm-ascend-v0.13.0" -> "vllm-ascend"
    folder = image_name.split('-')[0]
    # For multi-word families like "vllm-ascend", keep prefix up to version segment
    parts = image_name.split("-")
    family_parts = []
    for p in parts:
        # stop at version segment: starts with digit or 'v' followed by digit
        if p[0].isdigit() or (p.startswith("v") and len(p) > 1 and p[1].isdigit()):
            break
        family_parts.append(p)
    folder = "-".join(family_parts) if family_parts else image_name.split('-')[0]
    path_in_repo = f"{folder}/{tarball_path.name}"

    print(f"⬆️  Uploading to ModelScope {repo_id}/{path_in_repo}")
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            api.upload_file(
                path_or_fileobj=str(tarball_path),
                path_in_repo=path_in_repo,
                repo_id=repo_id,
                repo_type="dataset",
                commit_message=f"Add {image_name}",
            )
            break
        except Exception as e:
            print(f"⚠️  Upload attempt {attempt}/{max_retries} failed: {e}")
            if attempt == max_retries:
                print("❌ Upload failed after all retries!")
                sys.exit(1)

    # Build direct download URL
    download_url = f"https://modelscope.cn/datasets/{repo_id}/resolve/master/{path_in_repo}"
    print(f"   URL: {download_url}")

    # Update images.jsonl
    _update_images_jsonl(api, repo_id, image_name, image_config, path_in_repo, download_url, sha256, quay_digest)

    return download_url

def _update_images_jsonl(api, repo_id, image_name, image_config, path_in_repo, download_url, sha256=None, quay_digest=None):
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
        "sha256": sha256,
        "quayDigest": quay_digest,
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

    _sync_dataset_readme(api, repo_id)

def _sync_dataset_readme(api, repo_id):
    """Upload modelscope-readme.md as the dataset README if its content has changed."""
    import urllib.request
    readme_src = Path(__file__).parent / "modelscope-readme.md"
    if not readme_src.exists():
        return

    local = readme_src.read_bytes()
    namespace, dataset = repo_id.split("/", 1)
    try:
        url = api.get_dataset_file_url(file_name="README.md", dataset_name=dataset, namespace=namespace)
        with urllib.request.urlopen(url) as resp:
            remote = resp.read()
        if remote == local:
            return
    except Exception:
        pass  # README missing on remote — upload it

    api.upload_file(
        path_or_fileobj=local,
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Sync README from modelscope-readme.md",
    )
    print("📝 README.md synced to ModelScope")

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
    parser.add_argument("--no-deps", action="store_true", help="Only process the target image, skip dependencies")
    parser.add_argument("--no-pull", action="store_true", help="Skip docker pull before saving (use existing local image)")
    parser.add_argument("--upload-only", action="store_true", help="Skip save, upload existing <image-name>.tar.gz to ModelScope")
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
    if args.no_deps and args.target:
        build_order = [args.target]

    print(f"🚀 Build order: {' -> '.join(build_order)}")
    
    for image_name in build_order:
        if not args.no_build:
            build_image(image_name, config['images'][image_name], config['images'])
        quay_digest = None
        if args.push or args.rc:
            quay_digest = push_image(image_name, config['images'][image_name], rc=args.rc)
        if not args.rc and (args.push or args.save or args.upload_only or args.no_build):
            modelscope_url = None
            sha256 = None
            if args.upload_only:
                tarball = Path(f"{image_name}.tar.gz")
                if not tarball.exists():
                    print(f"❌ Tarball not found: {tarball}")
                    sys.exit(1)
                sha256 = sha256_file(tarball)
                print(f"   SHA256: {sha256}")
                modelscope_url = modelscope_upload(image_name, config['images'][image_name], tarball, sha256, quay_digest)
            elif args.save:
                tarball, sha256 = save_image(image_name, config['images'][image_name], no_pull=args.no_pull)
                modelscope_url = modelscope_upload(image_name, config['images'][image_name], tarball, sha256, quay_digest)
                tarball.unlink()
                print(f"🗑️  Deleted local tarball {tarball}")
            write_catalog_entry(image_name, config['images'][image_name], config['images'], modelscope_url, sha256, quay_digest)
        if args.delete:
            delete_image(config['images'][image_name])

    print("✅ All builds completed!")

if __name__ == "__main__":
    main()
