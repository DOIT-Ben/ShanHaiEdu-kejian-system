/**
 * Mock 世界的稳定 ID 目录。
 * e2e 与单测直接引用这些常量构造 URL；全部为合法 UUID（api-conventions.md）。
 */
export function uuid(n: number, prefix = 0): string {
  const head = String(prefix).padStart(8, "0");
  const tail = String(n).padStart(12, "0");
  return `${head}-0000-4000-8000-${tail}`;
}

export const ID = {
  userTeacher: uuid(1),
  userContentAdmin: uuid(2),
  userModelAdmin: uuid(3),
  userSystemAdmin: uuid(4),

  projAlpha: uuid(101),
  projEmpty: uuid(102),
  projAuto: uuid(103),

  materialAlpha: uuid(150),

  lessonA1: uuid(201),
  lessonA2: uuid(202),
  lessonA3: uuid(203),

  // lessonA2 的节点运行（工作台主演示对象）
  nrLessonPlanA2: uuid(301),
  nrIntroOptionsA2: uuid(302),
  nrIntroSelectionA2: uuid(303),
  nrPptOutlineA2: uuid(304),
  nrPptCoverA2: uuid(305),
  nrPptBodyA2: uuid(306),
  nrPptExportA2: uuid(307),
  nrVideoScriptA2: uuid(308),
  nrVideoStoryboardA2: uuid(309),
  nrVideoStyleA2: uuid(310),
  nrVideoAssetsA2: uuid(311),
  nrVideoClipsA2: uuid(312),
  nrVideoComposeA2: uuid(313),

  avLessonPlanA2: uuid(401),
  avIntroOptionsA2: uuid(402),
  avPptOutlineA2: uuid(403),
  avVideoScriptA2: uuid(404),
  avVideoStoryboardA2: uuid(405),

  videoProjectA2: uuid(501),
  shotA2_1: uuid(511),
  shotA2_2: uuid(512),
  shotA2_3: uuid(513),

  pageCoverA2: uuid(601),
  pageBody1A2: uuid(602),
  pageBody2A2: uuid(603),
  pageBody3A2: uuid(604),

  packageVideoAssetsA2: uuid(701),
  batchFromPackage: uuid(702),
  batchIndependent: uuid(703),

  providerText: uuid(801),
  providerImage: uuid(802),
  providerVideo: uuid(803),
  providerVideoBackup: uuid(804),
  providerTts: uuid(805),
  providerLayout: uuid(806),

  contentPkgLessonPlan: uuid(901),
  contentPkgIntroRules: uuid(902),
  contentPkgPptManual: uuid(903),

  workflowMain: uuid(950),
} as const;
