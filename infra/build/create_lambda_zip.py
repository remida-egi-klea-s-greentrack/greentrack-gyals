#!/usr/bin/env python3
"""Create Lambda deployment package ZIP file."""
import os
import zipfile
from pathlib import Path

def create_lambda_zip():
    """Create ZIP file with all dependencies and app code."""
    package_dir = Path(__file__).parent / "package"
    app_dir = Path(__file__).parent.parent.parent / "app"  # ../../app
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures"  # ../../fixtures
    zip_path = Path(__file__).parent / "lambda.zip"
    
    # Remove old ZIP if exists
    if zip_path.exists():
        zip_path.unlink()
        print(f"🗑️  Removed old {zip_path.name}")
    
    print(f"📦 Creating Lambda package from {package_dir}")
    
    # Create ZIP with compression
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        file_count = 0
        
        # 1. Add dependencies from package directory
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                # Calculate relative path (remove 'package/' prefix)
                arcname = file_path.relative_to(package_dir)
                
                zipf.write(file_path, arcname)
                file_count += 1
                
                if file_count % 100 == 0:
                    print(f"  Added {file_count} files...")
        
        print(f"✅ Added {file_count} dependencies")
        
        # 2. Add application code from app directory
        app_file_count = 0
        for root, dirs, files in os.walk(app_dir):
            # Skip __pycache__, tests, and frontend
            dirs[:] = [d for d in dirs if d not in ['__pycache__', 'tests', 'frontend', '.pytest_cache']]
            
            for file in files:
                # Skip .pyc files
                if file.endswith('.pyc'):
                    continue
                    
                file_path = Path(root) / file
                # Keep 'app/' prefix in archive
                arcname = file_path.relative_to(app_dir.parent)
                
                zipf.write(file_path, arcname)
                app_file_count += 1
        
        print(f"✅ Added {app_file_count} app files")
        
        # 3. Add fixtures directory
        fixtures_file_count = 0
        if fixtures_dir.exists():
            for root, dirs, files in os.walk(fixtures_dir):
                for file in files:
                    file_path = Path(root) / file
                    # Keep 'fixtures/' prefix in archive
                    arcname = file_path.relative_to(fixtures_dir.parent)
                    
                    zipf.write(file_path, arcname)
                    fixtures_file_count += 1
            
            print(f"✅ Added {fixtures_file_count} fixture files")
        
        print(f"✅ Total: {file_count + app_file_count + fixtures_file_count} files")
    
    # Show file size
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"📊 ZIP size: {size_mb:.2f} MB")
    print(f"✅ Lambda package created: {zip_path}")
    
    return zip_path

if __name__ == "__main__":
    create_lambda_zip()
