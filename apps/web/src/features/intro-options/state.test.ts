import { describe, expect, it } from "vitest";
import { introOptions } from "@/features/intro-options/data";
import {
  adoptPreviewedIntroOption,
  isPreviewAdopted,
  previewIntroOption,
  readIntroOptionsDraft,
  regeneratePreviewedIntroOption,
  resolveIntroOption,
  returnToAdoptedIntroOption,
} from "@/features/intro-options/state";

const firstOption = introOptions[0];
const secondOption = introOptions[1];

if (!firstOption || !secondOption) throw new Error("测试需要至少两套课堂导入方案");

describe("intro option draft state", () => {
  it("兼容旧草稿中的 selectedKey 和 adopted 字段", () => {
    const draft = readIntroOptionsDraft(
      { adopted: true, selectedKey: secondOption.key },
      firstOption.key,
    );

    expect(draft.previewKey).toBe(secondOption.key);
    expect(draft.adoptedKey).toBe(secondOption.key);
    expect(isPreviewAdopted(draft)).toBe(true);
  });

  it("只切换预览方案时保留当前正式采用方案", () => {
    const adopted = adoptPreviewedIntroOption(readIntroOptionsDraft(undefined, firstOption.key));
    const previewed = previewIntroOption(adopted, secondOption.key);

    expect(previewed.adoptedKey).toBe(firstOption.key);
    expect(previewed.previewKey).toBe(secondOption.key);
    expect(isPreviewAdopted(previewed)).toBe(false);
    expect(previewed).toMatchObject({ adopted: true, selectedKey: firstOption.key });
  });

  it("重新生成预览方案后产生可见新版本，但不会自动正式采用", () => {
    const adopted = adoptPreviewedIntroOption(readIntroOptionsDraft(undefined, firstOption.key));
    const regenerated = regeneratePreviewedIntroOption(
      adopted,
      firstOption,
      "增加百格窗的观察过程，减少旁白",
    );

    expect(regenerated.revisions[firstOption.key]).toBe(1);
    expect(isPreviewAdopted(regenerated)).toBe(false);
    const regeneratedOption = resolveIntroOption(firstOption, regenerated);
    expect(regeneratedOption.concept).toContain("增加百格窗的观察过程");
    expect(regeneratedOption.hook).toContain("先请学生说出观察");
    expect(regeneratedOption.firstQuestion).toContain("先说说你观察到了什么");
    expect(regeneratedOption.handoff).toContain("不再补充旁白");
    expect(regeneratedOption.medium).toBe("图片 + 提问");
    expect(regeneratedOption.duration).toBe(firstOption.duration - 10);

    const adoptedVersion = returnToAdoptedIntroOption(regenerated);
    expect(isPreviewAdopted(adoptedVersion)).toBe(true);
    expect(resolveIntroOption(firstOption, adoptedVersion).concept).toBe(firstOption.concept);
  });

  it("忽略持久化数据中的非法修订号", () => {
    const draft = readIntroOptionsDraft(
      {
        adopted: true,
        adoptedKey: firstOption.key,
        adoptedRevision: Number.NaN,
        previewKey: firstOption.key,
        previewRevision: -1,
        revisions: { [firstOption.key]: 2 },
      },
      firstOption.key,
    );

    expect(draft.adoptedRevision).toBe(2);
    expect(draft.previewRevision).toBe(2);
  });

  it("忽略与外层方案 key 不一致的完整修订内容", () => {
    const draft = readIntroOptionsDraft(
      {
        customOptionByRevision: {
          [firstOption.key]: { "1": secondOption },
        },
        previewKey: firstOption.key,
        previewRevision: 1,
        revisions: { [firstOption.key]: 1 },
      },
      firstOption.key,
    );

    expect(resolveIntroOption(firstOption, draft, 1)).toEqual(firstOption);
  });
});
