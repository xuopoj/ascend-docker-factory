# Ascend Docker Factory - Development Log

## Completed TODOs

### 1. dockerfile-compose.yaml Scope Limitation ✅ (2025-12-10)
   - **Decision**: Keep compose file for base/framework images only
   - **Solution**:
     - Removed app entries (yolo, flask-api, chronos) from compose file
     - Added vLLM as inference runtime/framework image
     - Kept base images: python, cann, pytorch-npu, ml-basic
     - Kept framework-level tool: msit-msmodelslim
     - App-specific Dockerfiles remain in `projects/` directory for manual builds
   - **Rationale**:
     - Base images benefit from dependency management and topological sorting
     - vLLM is infrastructure for LLM serving, not an app
     - Apps are highly varied and require manual customization
     - Cleaner separation: compose = infrastructure, projects/ = applications

### 2. pip Mirror Configuration ✅ (2025-12-10)
   - **Decision**: Configure pip mirror globally in Python base image
   - **Solution**:
     - Added `PIP_INDEX_URL` build arg to `python.dockerfile` (default: Tsinghua mirror)
     - Set global pip config: `pip config set global.index-url` and timeout
     - Removed `-i` flags from `pytorch-npu.dockerfile`
     - Updated `dockerfile-compose.yaml` to pass `PIP_INDEX_URL` for Python images
   - **Benefits**:
     - No need for `-i` flag in every pip install command
     - All images based on Python inherit the mirror configuration
     - Easy to switch mirrors by changing build arg
     - Consistent timeout settings across all images

### 3. Network Debugging Tools Configuration ✅ (2025-12-10)
   - **Decision**: Make network debugging tools optional via build arg
   - **Solution**:
     - Added `INCLUDE_DEBUG_TOOLS` build arg to `python.dockerfile` (default: true)
     - Separated network tools installation into conditional RUN block
     - Tools include: net-tools, iputils-ping, telnet, netcat, nmap, traceroute, dnsutils
     - Updated `dockerfile-compose.yaml` to explicitly set the flag
   - **Benefits**:
     - Smaller images when debug tools not needed (~20-30MB savings)
     - Configurable per image via build arg
     - Maintains backward compatibility (default: true)
     - Cleaner separation of essential vs debug tools
     - Pattern can be reused for other optional components

### 4. Three-Tier Architecture Reorganization ✅ (2025-12-19)
   - **Decision**: Establish clear separation between templates, projects, and examples
   - **Solution**:
     - **Templates Layer** (`dockerfiles/`): Base/framework image templates (Python, CANN, PyTorch, etc.)
       - Built via `build.py` orchestration with dependency management
       - Defined in `dockerfile-compose.yaml`
     - **Projects Layer** (`projects/`): Application-specific projects
       - Moved standalone `*.dockerfile` files into their project directories:
         - `yolo.dockerfile` → `yolo/Dockerfile`
         - `minimind.dockerfile` → `minimind/Dockerfile`
         - `chronos-forecasting.dockerfile` → `chronos-forecasting/Dockerfile`
         - `flask.dockerfile` → `flask/Dockerfile`
       - Manual builds using base images as `FROM`
     - **Examples Layer** (`examples/`): Verified, complete Dockerfiles
       - Production-ready, copy-paste ready reference implementations
       - Flattened, single-file Dockerfiles combining multiple layers
   - **Documentation Updates**:
     - Added architecture section to README.md with clear table
     - Clarified that `dockerfile-compose.yaml` is only for base/framework images
   - **Benefits**:
     - Clear separation of concerns: templates vs applications vs examples
     - Easier to maintain and understand the codebase
     - Project Dockerfiles are now colocated with their code
     - Examples directory provides verified reference implementations
     - Cleaner git history with files in logical locations

---

## Current Architecture

### CANN Installation (`dockerfiles/cann.dockerfile`)

**Direct Component Installation** - No external scripts, simple if-based logic:

```dockerfile
RUN --mount=type=bind,source=packages/${CANN_VERSION},target=/tmp/packages \
    cd /tmp/packages && \
    chmod +x *.run && \
    # Install NNAE or Toolkit (mutually exclusive - NNAE is simplified toolkit)
    if echo "${INSTALL_COMPONENTS}" | grep -q "nnae"; then \
        ./Ascend-cann-nnae_${CANN_VERSION}_linux-*.run --install --quiet; \
    elif echo "${INSTALL_COMPONENTS}" | grep -q "toolkit"; then \
        ./Ascend-cann-toolkit_${CANN_VERSION}_linux-*.run --install --quiet; \
    fi && \
    # Install optional components
    if echo "${INSTALL_COMPONENTS}" | grep -q "kernels"; then \
        ./Ascend-cann-kernels-${CHIP_TYPE}_${CANN_VERSION}_linux-*.run --install --quiet; \
    fi && \
    if echo "${INSTALL_COMPONENTS}" | grep -q "nnal"; then \
        ./Ascend-cann-nnal_${CANN_VERSION}_linux-*.run --install --quiet; \
    fi
```

**Component Logic**:
- **Toolkit vs NNAE**: Mutually exclusive (install NNAE if specified, else toolkit)
- **Kernels**: Chip-specific, installed if in `INSTALL_COMPONENTS`
- **NNAL**: Optional, installed if in `INSTALL_COMPONENTS`

**Build Args**:
- `CANN_VERSION`: Version like `8.3.RC1`
- `CHIP_TYPE`: `910b`, `310p`, or `a3`
- `INSTALL_COMPONENTS`: Comma-separated list (e.g., `toolkit,nnal,kernels`)

---

## Pending TODOs (For Next Session)

### Medium Priority

1. **Test Generated Dockerfiles**
   - Build test images for each configuration combination
   - Verify NNAL installation works in practice
   - Test component dependency enforcement
   - Verify pip mirror configuration works

2. **Enhanced Validation**
   - Add CANN version compatibility checks with chip types
   - Warn about known issues with specific version combinations
   - Validate PyTorch version compatibility with torch_npu

3. **Documentation**
   - Document component dependencies in README
   - Add troubleshooting guide for common build errors
   - Create examples for common use cases
   - Document pip mirror switching (PyPI, Aliyun, Tsinghua)

---
