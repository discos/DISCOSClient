import unittest
import json
from pathlib import Path
from importlib.resources import files
from referencing import Registry
from referencing.jsonschema import DRAFT7
from referencing.exceptions import Unresolvable
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError, ValidationError


class TestSchemas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = files("discos_client") / "schemas"
        cls.metaschema = Draft7Validator.META_SCHEMA

        schemas = [s.relative_to(cls.base) for s in cls.base.rglob("*.json")]
        resources = {}
        for schema in schemas:
            content = \
                json.loads(Path(cls.base / schema).read_text(encoding="utf-8"))
            resources[schema.as_posix()] = DRAFT7.create_resource(content)

        registry = Registry().with_resources(resources.items())
        registry = registry.with_resource(
            cls.metaschema["$id"],
            DRAFT7.create_resource(cls.metaschema)
        )

        cls.schemas = schemas
        cls.resources = resources
        cls.registry = registry

    def test_definitions(self):
        validator = Draft7Validator(self.metaschema, registry=self.registry)
        for schema_path in self.schemas:
            if not str(schema_path).startswith("definitions/"):
                continue
            schema = self.resources[schema_path.as_posix()].contents
            try:
                validator.check_schema(schema)
                validator.validate(schema)
            except (SchemaError, ValidationError, Unresolvable) as e:
                self.fail(f"Error in definition {schema_path}: {e}")

    def test_messages(self):
        messages_dir = Path(__file__).parent / "messages"

        for message_file in messages_dir.rglob("*.json"):
            rel_path = message_file.relative_to(messages_dir)
            base, sep, obj_name = rel_path.stem.partition(".")
            parent = rel_path.parent.stem

            schema_name = f"{parent}/{base}.json"
            matching_schema = next(
                s for s in self.schemas if s.as_posix() == schema_name
            )

            schema = self.resources[matching_schema.as_posix()].contents
            validator = Draft7Validator(schema, registry=self.registry)

            try:
                with open(message_file, "r", encoding="utf-8") as f:
                    message_content = json.load(f)
                message = \
                    {obj_name: message_content} if sep else message_content
                validator.validate(message)
            except (SchemaError, Unresolvable) as e:
                self.fail(f"Error in schema {schema_name}: {e}")
            except ValidationError as e:
                self.fail(f"Error in message {message_file.name}: {e}")


if __name__ == '__main__':
    unittest.main()
