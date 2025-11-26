#!/usr/bin/env bash
set -euo pipefail

# Get arguments from environment or defaults
CANN_VERSION="${CANN_VERSION:-8.2.RC1}"
CHIP_TYPE="${CHIP_TYPE:-unknown}"
INSTALL_COMPONENTS="${INSTALL_COMPONENTS:-toolkit,nnal,kernels}"

# install path
PREFIX="/usr/local/Ascend"
mkdir -p "${PREFIX}"


echo "Installing Ascend CANN ${CANN_VERSION} for chip ${CHIP_TYPE}"
echo "Components to install: ${INSTALL_COMPONENTS}"

# Parse components into array
IFS=',' read -ra COMPONENTS <<< "${INSTALL_COMPONENTS}"

# Function to check if component should be installed
should_install_component() {
    local component="$1"
    for comp in "${COMPONENTS[@]}"; do
        if [[ "${comp}" == "${component}" ]]; then
            return 0
        fi
    done
    return 1
}

# Function to find installer file for component and chip type
find_installer() {
    local component="$1"
    local pattern=""
    
    case "${component}" in
        "toolkit")
            pattern="Ascend-cann-toolkit_${CANN_VERSION}_linux-*.run"
            ;;
        "nnal")
            pattern="Ascend-cann-nnal_${CANN_VERSION}_linux-*.run"
            ;;
        "nnae")
            pattern="Ascend-cann-nnae_${CANN_VERSION}_linux-*.run"
            ;;
       "mindx-toolbox")
            # MindX Toolbox has its own versioning, find any available
            pattern="Ascend-mindx-toolbox_*_linux-*.run"
            ;;
        "kernels")
            # Handle chip-specific kernels
            case "${CHIP_TYPE}" in
                "310p")
                    pattern="Ascend-cann-kernels-310p_${CANN_VERSION}_linux-*.run"
                    ;;
                "910b")
                    pattern="Ascend-cann-kernels-910b_${CANN_VERSION}_linux-*.run"
                    ;;
                "a3"|"atlas-a3")
                    pattern="Atlas-A3-cann-kernels_${CANN_VERSION}_linux-*.run"
                    ;;
                *)
                    # Generic fallback - try any kernels package
                    pattern="*cann-kernels*_${CANN_VERSION}_linux-*.run"
                    ;;
            esac
            ;;
        *)
            echo "Warning: Unknown component '${component}'"
            return 1
            ;;
    esac
    
    # Find matching file
    set -- /tmp/packages/${pattern}
    if [ -f "$1" ]; then
        echo "$1"
        return 0
    else
        return 1
    fi
}

install_from_runfile() {
    tmpdir="$(mktemp -d)"
    cd "${tmpdir}"

    # Clear environment variables beforehand
    export LD_LIBRARY_PATH=""
    export PYTHONPATH=""

    # Install toolkit first (required by other components)
    if should_install_component "toolkit"; then
        if installer=$(find_installer "toolkit"); then
            echo "Installing toolkit from: ${installer}"
            cp "${installer}" toolkit.run
            bash toolkit.run --install --quiet
            . /usr/local/Ascend/ascend-toolkit/set_env.sh
        else
            echo "Error: Toolkit installer not found for version ${CANN_VERSION}"
            exit 1
        fi
    fi

    # Install nnae
    if should_install_component "nnae"; then
        if installer=$(find_installer "nnae"); then
            echo "Installing nnae from: ${installer}"
            cp "${installer}" nnae.run
            bash nnae.run --install --quiet
            . /usr/local/Ascend/nnae/set_env.sh
        else
            echo "Warning: NNAE installer not found for version ${CANN_VERSION}; skipping."
        fi
    fi

    # Install MindX Toolbox
    if should_install_component "mindx-toolbox"; then
        if installer=$(find_installer "mindx-toolbox"); then
            echo "Installing MindX Toolbox from: ${installer}"
            cp "${installer}" mindx-toolbox.run
            bash mindx-toolbox.run --install --quiet
        else
            echo "Warning: MindX Toolbox installer not found for version ${CANN_VERSION}; skipping."
        fi
    fi

    
    # Install kernels (chip-specific)
    if should_install_component "kernels"; then
        if installer=$(find_installer "kernels"); then
            echo "Installing kernels for ${CHIP_TYPE} from: ${installer}"
            cp "${installer}" kernels.run
            bash kernels.run --install --quiet
        else
            echo "Warning: Kernels installer not found for chip ${CHIP_TYPE} and version ${CANN_VERSION}; skipping."
        fi
    fi

    # Install nnal
    if should_install_component "nnal"; then
        if installer=$(find_installer "nnal"); then
            echo "Installing nnal from: ${installer}"
            cp "${installer}" nnal.run
            bash nnal.run --install --quiet
        else
            echo "Warning: NNAL installer not found for version ${CANN_VERSION}; skipping."
        fi
    fi

    rm -rf "${tmpdir}"
    echo "Installation completed successfully!"
}

install_from_runfile