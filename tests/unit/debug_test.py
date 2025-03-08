"""Debug test to identify import issues."""

import os
import sys

# Print environment info
print(f"Current dir: {os.getcwd()}")
print(f"Python path: {sys.path}")

# Try direct import of each module
print("\nTrying direct imports...")

try:
    import pygovpub
    print(f"SUCCESS: imported pygovpub from {pygovpub.__file__}")
    
    # Try auth module
    try:
        import pygovpub.auth
        print(f"SUCCESS: imported pygovpub.auth from {pygovpub.auth.__file__}")
        
        # Try specific modules
        try:
            from pygovpub.auth import models
            print(f"SUCCESS: imported models from {models.__file__}")
        except ImportError as e:
            print(f"FAILED: importing models: {e}")
            
        try:
            from pygovpub.auth import auth_manager
            print(f"SUCCESS: imported auth_manager from {auth_manager.__file__}")
        except ImportError as e:
            print(f"FAILED: importing auth_manager: {e}")
            
        try:
            from pygovpub.auth import rate_limiter
            print(f"SUCCESS: imported rate_limiter from {rate_limiter.__file__}")
        except ImportError as e:
            print(f"FAILED: importing rate_limiter: {e}")
            
    except ImportError as e:
        print(f"FAILED: importing pygovpub.auth: {e}")
        
except ImportError as e:
    print(f"FAILED: importing pygovpub: {e}")

# Try importing a standard library module for comparison
try:
    import datetime
    print(f"SUCCESS: imported datetime from {datetime.__file__}")
except ImportError as e:
    print(f"FAILED: importing datetime: {e}")

# Simple unittest for pytest
if __name__ == "__main__":
    import unittest
    
    class TestDebugImports(unittest.TestCase):
        def test_debug(self):
            self.assertTrue(True)
    
    unittest.main()