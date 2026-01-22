"""
Script to create the complete directory structure
"""
import os
from pathlib import Path

def create_directory_structure():
    """Create all necessary directories and files"""
    
    # Base directories
    directories = [
        'models',
        'data',
        'utils',
        'assets',
        'tests',
        'logs'
    ]
    
    print("📁 Creating directory structure...")
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created: {directory}/")
        
        # Create __init__.py for Python packages
        if directory in ['models', 'data', 'utils']:
            init_file = Path(directory) / '__init__.py'
            if not init_file.exists():
                init_file.touch()
                print(f"✅ Created: {init_file}")
    
    # Create config.py if it doesn't exist
    if not Path('config.py').exists():
        print("⚠️  config.py not found - please create it")
    
    # Create styles.css if it doesn't exist
    styles_path = Path('assets') / 'styles.css'
    if not styles_path.exists():
        print("⚠️  assets/styles.css not found - please create it")
    
    # Create .gitignore
    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        with open(gitignore_path, 'w') as f:
            f.write("""# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Environment
.env
*.env

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db

# Streamlit
.streamlit/secrets.toml
""")
        print("✅ Created: .gitignore")
    
    print("\n✨ Directory structure created successfully!")
    print("\n📋 Next steps:")
    print("1. Ensure all .py files are in their correct directories")
    print("2. Run: python setup_structure.py")
    print("3. Run: streamlit run app.py")

if __name__ == "__main__":
    create_directory_structure()