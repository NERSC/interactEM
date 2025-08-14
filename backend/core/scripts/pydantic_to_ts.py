import pathlib
import re

from pydantic2ts import generate_typescript_defs


def deduplicate_enums(file_path: str, enum_base_names: list[str]):
    """
    Reads a TypeScript file, finds and removes duplicate enums generated
    by pydantic2ts, and updates all references to point to the canonical enum.
    This version correctly handles and consolidates all duplicate definitions.

    Args:
        file_path: The path to the TypeScript file to clean.
        enum_base_names: A list of the base names of the enums to deduplicate
                         (e.g., ['NodeType', 'PortType']).
    """
    print(f"Cleaning up duplicate enums in {file_path}...")

    with open(file_path) as f:
        content = f.read()

    # First, replace all usages of numbered enums so they all use the base name.
    # This makes all references and definitions consistent.
    for base_name in enum_base_names:
        usage_pattern = re.compile(r"\b" + re.escape(base_name) + r"\d+\b")
        content = usage_pattern.sub(base_name, content)

    # Now, find the first definition of each enum, remove all definitions,
    # and prepare to add the canonical one back.
    canonical_definitions = []
    for base_name in enum_base_names:
        # This pattern finds the entire `export enum Name {...}` block.
        # It no longer looks for numbers, as they have been removed.
        definition_pattern = re.compile(
            r"export enum " + re.escape(base_name) + r" {[^}]*?}", re.DOTALL
        )

        # Find all occurrences
        found_definitions = definition_pattern.findall(content)

        if found_definitions:
            # Store the first one we find as the one to keep.
            # We add a couple of newlines for nice formatting.
            canonical_definitions.append(found_definitions[0] + "\n")

            # Remove ALL occurrences from the content.
            content = definition_pattern.sub("", content)

    # Clean up any excessive newlines that might result from the removal
    content = re.sub(r"\n{3,}", "\n\n", content.strip())

    # Append the unique, canonical definitions at the end of the file.
    if canonical_definitions:
        content += "\n\n" + "\n".join(canonical_definitions)

    # Write the cleaned content back to the file
    with open(file_path, "w") as f:
        f.write(content.strip() + "\n")

    print("Cleanup complete.")


# 0. Determine the repository root relative to this file
repo_root = pathlib.Path(__file__).resolve().parents[3]
output_path = repo_root / "frontend" / "interactEM" / "src" / "types" / "gen.ts"
json2ts_cmd = 'json2ts --inferStringEnumKeysFromValues --enableConstEnums false'

# 1. Generate the TypeScript file from Pydantic models
print("Generating TypeScript definitions...")
generate_typescript_defs("interactem.core.models._export", str(output_path), (), json2ts_cmd)
print("Generation complete.")

# 2. Run the post-processing step to clean the generated file
enum_bases_to_clean = ["NodeType", "PortType", "OperatorEventType", "PipelineEventType"]
deduplicate_enums(str(output_path), enum_bases_to_clean)
