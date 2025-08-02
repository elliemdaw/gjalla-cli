"""
Setup script for Spec Standardization CLI tool.
"""

from setuptools import setup, find_packages
from setuptools.command.install import install
from pathlib import Path
import subprocess
import sys

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text().strip().split('\n')


class PostInstallCommand(install):
    """Custom install command to run post-installation tasks."""
    
    def run(self):
        # Run the standard install
        install.run(self)
        
        # Run post-install tasks
        try:
            self._install_spacy_model()
        except Exception as e:
            print(f"⚠️  Post-install warning: {e}")
            print("   You may need to manually install spaCy model with:")
            print("   python -m spacy download en_core_web_sm")
    
    def _install_spacy_model(self):
        """Install spaCy English model if not already present."""
        try:
            import spacy
            try:
                spacy.load("en_core_web_sm")
                print("✓ spaCy model 'en_core_web_sm' already installed")
                return
            except OSError:
                print("Installing spaCy model 'en_core_web_sm'...")
                subprocess.check_call([
                    sys.executable, "-m", "spacy", "download", "en_core_web_sm"
                ])
                print("✓ Successfully installed spaCy model 'en_core_web_sm'")
        except ImportError:
            print("⚠️  spaCy not installed, skipping model download")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Failed to install spaCy model: {e}")
            print("   You can install it manually with: python -m spacy download en_core_web_sm")

setup(
    name="gjalla",
    version="0.1.0",
    author="Ellie",
    author_email="ellie@gjalla.io",
    description="CLI tool for organizing, aggregating, and standardizing requirements and architecture information from markdowns written by agentic coding tools.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/elliemdaw/gjalla-cli",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Documentation",
        "Topic :: Software Development :: Documentation",
        "Topic :: Text Processing :: Markup",
    ],
    python_requires=">=3.8",
    install_requires=[
        "cryptography>=3.4.8",
        "requests>=2.25.1",
        "click>=8.0.0",
        "pydantic>=1.8.0",
        "rich>=10.0.0",
        "pathlib2>=2.3.6; python_version<'3.4'",
        "spacy>=3.4.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.10.0",
            "black>=21.0.0",
            "flake8>=3.8.0",
            "mypy>=0.812",
        ],
    },
    cmdclass={
        'install': PostInstallCommand,
    },
    entry_points={
        "console_scripts": [
            "gjalla=cli_tools.main_cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "gjalla": [
            "templates/*.md",
            "config/*.json",
        ],
    },
    zip_safe=False,
    keywords="documentation markdown validation standardization cli ai",
    project_urls={
        "Bug Reports": "https://github.com/elliemdaw/gjalla-cli/issues",
        "Source": "https://github.com/elliemdaw/gjalla-cli"
    },
)