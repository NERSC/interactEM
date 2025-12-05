import { Project, SyntaxKind } from "ts-morph";

/**
 * Deduplicates enum definitions in a TypeScript file.
 * When pydantic2ts generates TypeScript from Pydantic models, it sometimes creates
 * multiple definitions of the same enum with numbered suffixes (e.g., NodeType, NodeType2).
 * This script consolidates them into a single canonical definition.
 */
async function deduplicateEnums(filePath: string): Promise<void> {
  console.log(`Cleaning up duplicate enums in ${filePath}...`);

  const project = new Project();
  const sourceFile = project.addSourceFileAtPath(filePath);

  const enumsToClean = [
    "NodeType",
    "PortType",
    "OperatorEventType",
    "DeploymentEventType",
    "ParameterSpecType",
  ];

  for (const baseName of enumsToClean) {
    const enumDeclarations = sourceFile
      .getEnums()
      .filter((e) => e.getName().match(new RegExp(`^${baseName}\\d*$`)));

    if (enumDeclarations.length === 0) {
      continue;
    }

    // Find the canonical enum (without numbers), or use the first one
    const canonicalEnum =
      enumDeclarations.find((e) => e.getName() === baseName) ||
      enumDeclarations[0];
    const enumsToRemove = enumDeclarations.filter((e) => e !== canonicalEnum);

    // Update all numbered enum references to point to the base name
    sourceFile.getDescendantsOfKind(SyntaxKind.Identifier).forEach((node) => {
      const text = node.getText();
      const match = text.match(new RegExp(`^${baseName}\\d+$`));
      if (match) {
        node.replaceWithText(baseName);
      }
    });

    // Remove duplicate enum declarations
    enumsToRemove.forEach((enumDecl) => {
      enumDecl.remove();
    });

    console.log(
      `  ✓ Consolidated ${enumDeclarations.length} definition(s) for ${baseName}`
    );
  }

  // Save the cleaned file
  await sourceFile.save();
  console.log("Cleanup complete.");
}

// Execute
const filePath = "src/types/gen.ts";
await deduplicateEnums(filePath);
