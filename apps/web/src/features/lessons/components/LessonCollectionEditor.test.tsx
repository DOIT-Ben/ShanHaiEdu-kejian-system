import { TooltipProvider } from "@radix-ui/react-tooltip";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import type { LessonDto } from "@/features/lessons/api/lessonsApi";
import { LessonCollectionEditor } from "@/features/lessons/components/LessonCollectionEditor";

const lesson = {
  id: "lesson-1",
  position: 1,
  title: "百分数的意义",
  scope_summary: "认识百分数",
  objective_summary: "能够读写百分数",
  estimated_minutes: 40,
  branches: [
    { branch_key: "lesson_plan", enabled: true, settings: {}, workflow_status: "not_ready" },
    { branch_key: "video", enabled: false, settings: {}, workflow_status: "disabled" },
  ],
} as LessonDto;

const secondLesson = {
  ...lesson,
  id: "lesson-2",
  position: 2,
  title: "百分数的应用",
  branches: lesson.branches.map((branch) => ({ ...branch })),
};

const thirdLesson = {
  ...lesson,
  id: "lesson-3",
  position: 3,
  title: "单元复习",
  branches: lesson.branches.map((branch) => ({ ...branch })),
};

const collectionEtag = '"collection-v1"';
const lessonEtags = {
  "lesson-1": '"lesson-v1"',
  "lesson-2": '"lesson-v1"',
  "lesson-3": '"lesson-v1"',
};

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
}

function renderEditor(element: ReactElement) {
  return render(element, { wrapper: TooltipProvider });
}

describe("LessonCollectionEditor", () => {
  it("把课时字段和分支开关转换为合同写入意图", async () => {
    const user = userEvent.setup();
    const onSaveCollection = vi.fn();
    const onSaveBranches = vi.fn();
    renderEditor(
      <LessonCollectionEditor
        collectionEtag={collectionEtag}
        conflictMessage=""
        lessonEtags={lessonEtags}
        lessons={[lesson]}
        onSaveBranches={onSaveBranches}
        onSaveCollection={onSaveCollection}
      />,
    );

    const title = screen.getByLabelText("课时 1 名称");
    await user.clear(title);
    await user.type(title, "百分数初步认识");
    await user.click(screen.getByRole("checkbox", { name: "课堂视频" }));
    await user.click(screen.getByRole("button", { name: "保存百分数初步认识的分支" }));
    expect(onSaveBranches).toHaveBeenCalledWith(
      "lesson-1",
      expect.arrayContaining([expect.objectContaining({ branch_key: "video", enabled: true })]),
      '"lesson-v1"',
    );

    await user.click(screen.getByRole("button", { name: "保存课时集合" }));
    expect(onSaveCollection).toHaveBeenCalledWith(
      [expect.objectContaining({ id: "lesson-1", position: 1, title: "百分数初步认识" })],
      '"collection-v1"',
    );
  });

  it("集合草稿锁定开始编辑时的 ETag", async () => {
    const user = userEvent.setup();
    const onSaveCollection = vi.fn();
    const props = {
      lessonEtags: { "lesson-1": '"lesson-v1"' },
      lessons: [lesson],
      onSaveBranches: vi.fn(),
      onSaveCollection,
    };
    const view = renderEditor(
      <LessonCollectionEditor {...props} collectionEtag='"collection-v1"' />,
    );

    const title = screen.getByLabelText("课时 1 名称");
    await user.clear(title);
    await user.type(title, "尚未保存的集合草稿");
    view.rerender(<LessonCollectionEditor {...props} collectionEtag='"collection-v2"' />);
    await user.click(screen.getByRole("button", { name: "保存课时集合" }));

    expect(onSaveCollection).toHaveBeenCalledWith(
      [expect.objectContaining({ title: "尚未保存的集合草稿" })],
      '"collection-v1"',
    );
  });

  it("分支草稿锁定开始编辑时的课时 ETag", async () => {
    const user = userEvent.setup();
    const onSaveBranches = vi.fn();
    const props = {
      collectionEtag: '"collection-v1"',
      lessons: [lesson],
      onSaveBranches,
      onSaveCollection: vi.fn(),
    };
    const view = renderEditor(
      <LessonCollectionEditor {...props} lessonEtags={{ "lesson-1": '"lesson-v1"' }} />,
    );

    await user.click(screen.getByRole("checkbox", { name: "课堂视频" }));
    view.rerender(
      <LessonCollectionEditor {...props} lessonEtags={{ "lesson-1": '"lesson-v2"' }} />,
    );
    await user.click(screen.getByRole("button", { name: "保存百分数的意义的分支" }));

    expect(onSaveBranches).toHaveBeenCalledWith(
      "lesson-1",
      expect.arrayContaining([expect.objectContaining({ branch_key: "video", enabled: true })]),
      '"lesson-v1"',
    );
  });

  it("按展示顺序连续编号，并通过省略课时表达软归档", async () => {
    const user = userEvent.setup();
    const pendingSave = deferred();
    const onSaveCollection = vi.fn(() => pendingSave.promise);
    renderEditor(
      <LessonCollectionEditor
        collectionEtag={collectionEtag}
        lessonEtags={lessonEtags}
        lessons={[lesson, secondLesson, thirdLesson]}
        onSaveBranches={vi.fn()}
        onSaveCollection={onSaveCollection}
      />,
    );

    await user.click(screen.getByRole("button", { name: "上移百分数的应用" }));
    await user.click(screen.getByRole("button", { name: "移除百分数的意义" }));
    await user.click(screen.getByRole("button", { name: "保存课时集合" }));

    expect(onSaveCollection).toHaveBeenCalledWith(
      [
        expect.objectContaining({ id: "lesson-2", position: 1 }),
        expect.objectContaining({ id: "lesson-3", position: 2 }),
      ],
      '"collection-v1"',
    );
  });

  it("至少保留一个课时", async () => {
    const user = userEvent.setup();
    renderEditor(
      <LessonCollectionEditor
        collectionEtag={collectionEtag}
        lessonEtags={lessonEtags}
        lessons={[lesson, secondLesson]}
        onSaveBranches={vi.fn()}
        onSaveCollection={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "移除百分数的意义" }));

    expect(screen.getByRole("button", { name: "移除百分数的应用" })).toBeDisabled();
  });

  it("集合保存后的重新获取不会覆盖未保存的分支草稿", async () => {
    const user = userEvent.setup();
    const collectionSave = deferred();
    const onSaveCollection = vi.fn(() => collectionSave.promise);
    const props = {
      collectionEtag,
      lessonEtags,
      onSaveBranches: vi.fn(),
      onSaveCollection,
    };
    const view = renderEditor(<LessonCollectionEditor {...props} lessons={[lesson]} />);

    await user.click(screen.getByRole("checkbox", { name: "课堂视频" }));
    const title = screen.getByLabelText("课时 1 名称");
    await user.clear(title);
    await user.type(title, "百分数初步认识");
    await user.click(screen.getByRole("button", { name: "保存课时集合" }));

    view.rerender(
      <LessonCollectionEditor {...props} lessons={[{ ...lesson, title: "百分数初步认识" }]} />,
    );
    await act(() => {
      collectionSave.resolve();
      return collectionSave.promise;
    });

    await waitFor(() => expect(screen.getByLabelText("课时 1 名称")).toHaveValue("百分数初步认识"));
    expect(screen.getByRole("checkbox", { name: "课堂视频" })).toBeChecked();
  });

  it("分支保存后的重新获取不会覆盖未保存的集合草稿", async () => {
    const user = userEvent.setup();
    const branchSave = deferred();
    const onSaveBranches = vi.fn(() => branchSave.promise);
    const props = {
      collectionEtag,
      lessonEtags,
      onSaveBranches,
      onSaveCollection: vi.fn(),
    };
    const view = renderEditor(<LessonCollectionEditor {...props} lessons={[lesson]} />);

    const title = screen.getByLabelText("课时 1 名称");
    await user.clear(title);
    await user.type(title, "尚未保存的本地标题");
    await user.click(screen.getByRole("checkbox", { name: "课堂视频" }));
    await user.click(screen.getByRole("button", { name: "保存尚未保存的本地标题的分支" }));

    view.rerender(
      <LessonCollectionEditor
        {...props}
        lessons={[
          {
            ...lesson,
            branches: lesson.branches.map((branch) =>
              branch.branch_key === "video" ? { ...branch, enabled: true } : branch,
            ),
          },
        ]}
      />,
    );
    await act(() => {
      branchSave.resolve();
      return branchSave.promise;
    });

    await waitFor(() =>
      expect(screen.getByLabelText("课时 1 名称")).toHaveValue("尚未保存的本地标题"),
    );
    expect(screen.getByRole("checkbox", { name: "课堂视频" })).toBeChecked();
  });
});
