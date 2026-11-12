#!/usr/bin/env python3
"""Create Lambda deployment package ZIP file."""
import os
import zipfile
from pathlib import Path

def create_lambda_zip():
    """Create ZIP file with all dependencies and app code."""
    package_dir = Path(__file__).parent / "package"
    zip_path = Path(__file__).parent / "lambda.zip"
    
    # Remove old ZIP if exists
    if zip_path.exists():
        zip_path.unlink()
        print(f"🗑️  Removed old {zip_path.name}")
    
    print(f"📦 Creating Lambda package from {package_dir}")
    
    # Create ZIP with compression
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        file_count = 0
        
        # Walk through package directory
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                # Calculate relative path (remove 'package/' prefix)
                arcname = file_path.relative_to(package_dir)
                
                zipf.write(file_path, arcname)
                file_count += 1
                
                if file_count % 100 == 0:
                    print(f"  Added {file_count} files...")
        
        print(f"✅ Added {file_count} files total")
    
    # Show file size
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"📊 ZIP size: {size_mb:.2f} MB")
    print(f"✅ Lambda package created: {zip_path}")
    
    return zip_path

if __name__ == "__main__":
    create_lambda_zip()
