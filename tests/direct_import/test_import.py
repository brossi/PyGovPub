def test_direct_import():
    import sys
    print(f"System paths: {sys.path}")
    
    # Try direct import of module file
    sys.path.insert(0, 'src')
    import pygovpub.config
    print(f"Config module: {pygovpub.config}")
    
    # Try auth module
    import pygovpub.auth.models
    print(f"Auth models module: {pygovpub.auth.models}")
    
    assert True
