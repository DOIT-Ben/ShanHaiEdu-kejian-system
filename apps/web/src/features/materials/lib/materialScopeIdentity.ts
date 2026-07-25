type ScopeVersion = { content?: unknown } | null | undefined;

export function materialScopeVersionMatches(
  version: ScopeVersion,
  materialId?: string,
  parseVersionId?: string,
) {
  if (!materialId || !parseVersionId) return false;
  const content = version?.content;
  if (typeof content !== "object" || content === null || Array.isArray(content)) return false;
  const record = content as Record<string, unknown>;
  return (
    record.source_material_id === materialId && record.material_parse_version_id === parseVersionId
  );
}
