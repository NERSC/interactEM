import pathlib

from pydantic2ts import generate_typescript_defs

# 0. Determine the repository root relative to this file
repo_root = pathlib.Path(__file__).resolve().parents[3]
output_path = repo_root / "frontend" / "interactEM" / "src" / "types" / "gen.ts"
json2ts_cmd = "json2ts --inferStringEnumKeysFromValues --enableConstEnums false"

# 1. Generate the TypeScript file from Pydantic models
print("Generating TypeScript definitions...")
generate_typescript_defs(
    "interactem.core.models._export", str(output_path), (), json2ts_cmd
)
print("Generation complete.")
