import yaml
import subprocess
import sys
import argparse
import os

REGISTRY_PREFIX = "xuopoj"

def run_command(cmd):
    print(f"🔨 [EXEC] {cmd}")
    # Force enable BuildKit for the --mount feature
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    ret = subprocess.call(cmd, shell=True, env=env)
    if ret != 0:
        print("❌ Build failed!")
        sys.exit(1)

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def build(args):
    config = load_config()
    target_id = args.target

    # Simple filter function
    def should_build(item):
        # If target_id is set, only build matching ID. Else build none.
        return target_id == item['id'] if target_id else False

    # ================= Level 1: CANN (With Hardware Meta) =================
    cann_id_map = {} 
    for cann in config['cann_bases']:
        image_tag = f"{REGISTRY_PREFIX}/cann:{cann['tag_suffix']}"
        cann_id_map[cann['id']] = image_tag

        if should_build(cann):
            print(f"\n📦 Building CANN [{cann['id']}] for [{cann['chip']}]")
            cmd = (
                f"docker build -t {image_tag} "
                f"-f Dockerfile.cann "
                f"--build-arg CANN_VERSION={cann['cann_version']} "
                f"--build-arg CHIP_TYPE={cann['chip']} "
                f"--build-arg INSTALL_COMPONENTS={cann.get('install_components', None)} "
                f"--build-arg DRIVER_VERSION={cann.get('driver_version', 'N/A')} "
                f"."
            )
            run_command(cmd)

    # ================= Level 2: PyTorch =================
    pt_id_map = {}
    for pt in config['pytorch_layers']:
        base_cann_id = pt['base_cann_id']
        base_image = cann_id_map.get(base_cann_id)
        
        if not base_image:
            print(f"⚠️ Skipping PyTorch layer {pt['id']} because base CANN skipped.")
            continue

        # Tag naming: pytorch-2.1.0-910b
        image_tag = f"{REGISTRY_PREFIX}/pytorch:{pt['torch_version']}-{base_cann_id.split('cann')[1]}"
        pt_id_map[pt['id']] = image_tag

        if should_build(pt):
            print(f"\n📦 Building PyTorch [{pt['id']}]")
            cmd = (
                f"docker build -t {image_tag} "
                f"-f Dockerfile.pytorch "
                f"--build-arg BASE_IMAGE={base_image} "
                f"--build-arg TORCH_VERSION={pt['torch_version']} "
                f"--build-arg TORCH_NPU_VERSION={pt['torch_npu_version']} "
                f"."
            )
            run_command(cmd)

    # ================= Level 3: Workloads (Routing) =================
    # Define strategies for different workload types

    for app in config.get('applications', []):
        base_image = pt_id_map.get(app['base_pt_id'])
        if not base_image: continue

        image_tag = f"{REGISTRY_PREFIX}/{app['id']}:{app.get('app_tag', 'latest')}"

        if should_build(app):
            print(f"\n📦 Building Workload [{app['id']}]")
            cmd = (
                f"docker build -t {image_tag} "
                f"-f {app.get("dockerfile")} "
                f"--build-arg BASE_IMAGE={base_image} "
                f"."
            )
            run_command(cmd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", help="Build specific ID (e.g., vllm-910b)")
    args = parser.parse_args()
    build(args)