def test_project_inspect_file_preserves_standard_library_api() -> None:
    import inspect

    assert inspect.isfunction(test_project_inspect_file_preserves_standard_library_api)
