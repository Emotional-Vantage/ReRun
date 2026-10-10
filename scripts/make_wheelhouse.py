import os
import sys
import docker
from pathlib import Path


def main():
    project_root = Path(__file__).parent.parent.absolute()
    wheelhouse_dir = project_root / "wheelhouse"
    wheelhouse_dir.mkdir(exist_ok=True)

    req_dir = project_root / "sandbox" / "images"
    req_file = req_dir / "requirements.wheelhouse.txt"

    requirements_content = (
        "torch==2.5.1+cpu\n"
        "numpy==1.26.4\n"
        "PyYAML==6.0.1\n"
        "autograd\n"
        "imageio\n"
        "scipy\n"
        "scikit-learn\n"
        "pandas\n"
        "matplotlib\n"
    )
    req_file.write_text(requirements_content)

    client = docker.from_env()

    print(f"Building wheelhouse in {wheelhouse_dir}...")
    try:
        # Run pip download in the base python 3.11 container to get Linux/Python 3.11 wheels
        container_output = client.containers.run(
            image="rerun-base:py311",
            command=[
                "pip",
                "download",
                "-d",
                "/wheelhouse",
                "--extra-index-url",
                "https://download.pytorch.org/whl/cpu",
                "-r",
                "/req/requirements.wheelhouse.txt",
            ],
            volumes={
                str(wheelhouse_dir): {"bind": "/wheelhouse", "mode": "rw"},
                str(req_dir): {"bind": "/req", "mode": "ro"},
            },
            remove=True,
            network_mode="bridge",
            user="1000:1000",
        )
        print("Wheelhouse built successfully.")
        if container_output:
            print(container_output.decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"Error building wheelhouse: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
