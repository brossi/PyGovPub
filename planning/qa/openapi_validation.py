"""OpenAPI documentation validation for PyGovPub."""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
import yaml

class ValidationError(BaseModel):
    """Validation error details."""
    path: str = Field(..., description="Path to the problematic endpoint")
    error: str = Field(..., description="Description of the error")
    suggestion: Optional[str] = Field(None, description="Suggested fix")

class DocumentationValidator:
    """Validates OpenAPI documentation completeness and quality."""

    def __init__(self, app_module: str):
        """Initialize validator with FastAPI app module."""
        self.app = self._import_app(app_module)
        self.schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            routes=self.app.routes,
            description=self.app.description
        )
        self.errors: List[ValidationError] = []

    def _import_app(self, module_path: str):
        """Import FastAPI app from module path."""
        sys.path.append(str(Path.cwd()))
        module = __import__(module_path, fromlist=['app'])
        return module.app

    def validate_all(self) -> List[ValidationError]:
        """Run all validation checks."""
        self.validate_routes()
        self.validate_models()
        self.validate_security()
        self.validate_examples()
        return self.errors

    def validate_routes(self):
        """Validate route documentation."""
        for route in self.app.routes:
            path = getattr(route, "path", "")
            if not path:
                continue

            # Check basic documentation
            if not route.description:
                self.errors.append(ValidationError(
                    path=path,
                    error="Missing route description",
                    suggestion="Add a description using the description parameter"
                ))

            if not getattr(route, "response_model", None):
                self.errors.append(ValidationError(
                    path=path,
                    error="Missing response model",
                    suggestion="Add response_model parameter to route decorator"
                ))

            # Check parameters
            for param in route.parameters:
                if not param.description:
                    self.errors.append(ValidationError(
                        path=f"{path}:{param.name}",
                        error="Missing parameter description",
                        suggestion=f"Add description for parameter {param.name}"
                    ))

    def validate_models(self):
        """Validate response/request model documentation."""
        for schema_name, schema in self.schema.get("components", {}).get("schemas", {}).items():
            # Check model description
            if "description" not in schema:
                self.errors.append(ValidationError(
                    path=f"schemas/{schema_name}",
                    error="Missing model description",
                    suggestion="Add class docstring or description in Config"
                ))

            # Check properties
            for prop_name, prop in schema.get("properties", {}).items():
                if "description" not in prop:
                    self.errors.append(ValidationError(
                        path=f"schemas/{schema_name}/{prop_name}",
                        error="Missing property description",
                        suggestion=f"Add Field description for {prop_name}"
                    ))

    def validate_security(self):
        """Validate security documentation."""
        security_schemes = self.schema.get("components", {}).get("securitySchemes", {})
        if not security_schemes:
            self.errors.append(ValidationError(
                path="security",
                error="Missing security schemes",
                suggestion="Add security_schemes to FastAPI app configuration"
            ))

    def validate_examples(self):
        """Validate example values in documentation."""
        for path, path_item in self.schema.get("paths", {}).items():
            for method, operation in path_item.items():
                # Check request body examples
                if "requestBody" in operation:
                    if "example" not in operation["requestBody"]["content"]["application/json"]["schema"]:
                        self.errors.append(ValidationError(
                            path=f"{path}.{method}.requestBody",
                            error="Missing request body example",
                            suggestion="Add example in model Config or request body"
                        ))

                # Check response examples
                for status, response in operation.get("responses", {}).items():
                    if "content" in response and "example" not in response["content"]["application/json"]["schema"]:
                        self.errors.append(ValidationError(
                            path=f"{path}.{method}.responses.{status}",
                            error="Missing response example",
                            suggestion="Add example in response model Config"
                        ))

def main():
    """Main validation function."""
    validator = DocumentationValidator("pygovpub.main")
    errors = validator.validate_all()

    if errors:
        print("\nDocumentation Validation Errors:")
        for error in errors:
            print(f"\n{error.path}:")
            print(f"  Error: {error.error}")
            if error.suggestion:
                print(f"  Suggestion: {error.suggestion}")
        sys.exit(1)
    else:
        print("\nDocumentation validation passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()
