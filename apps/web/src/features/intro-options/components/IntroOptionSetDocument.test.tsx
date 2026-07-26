import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IntroOptionSetDocument } from "@/features/intro-options/components/IntroOptionSetDocument";
import goldenProject from "../../../../../../contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json";

const content = goldenProject.intro_option_set as unknown as Record<string, unknown>;

describe("IntroOptionSetDocument", () => {
  it("renders science, application, and story as three exact groups", () => {
    render(<IntroOptionSetDocument content={content} />);

    expect(screen.getByRole("heading", { name: "科普导入" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "应用导入" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "故事导入" })).toBeVisible();
    expect(screen.getAllByText("3 套方案")).toHaveLength(3);
    expect(screen.getAllByRole("article")).toHaveLength(9);
  });

  it("edits teacher text while preserving identity and structure fields", () => {
    const onChange = vi.fn();
    render(<IntroOptionSetDocument content={content} editable onChange={onChange} />);
    const firstEditor = screen.getAllByLabelText("方案正文").at(0);
    const firstOption = goldenProject.intro_option_set.options.at(0);
    if (!firstEditor || !firstOption) throw new Error("Golden Intro option fixture is incomplete.");

    fireEvent.change(firstEditor, {
      target: { value: "教师调整后的课堂导入正文" },
    });

    const changed = onChange.mock.calls[0]?.[0] as typeof goldenProject.intro_option_set;
    const changedOption = changed.options.at(0);
    if (!changedOption) throw new Error("Edited Intro option is missing.");
    expect(changedOption.creative_concept).toBe("教师调整后的课堂导入正文");
    expect(changedOption.option_key).toBe(firstOption.option_key);
    expect(changedOption.primary_tendency).toBe(firstOption.primary_tendency);
    expect(changedOption.recommendation_score).toBe(firstOption.recommendation_score);
    expect(changed.source_intro_option_version_refs).toEqual(
      goldenProject.intro_option_set.source_intro_option_version_refs,
    );
  });

  it("adopts one exact option key from the approved display", () => {
    const onSelect = vi.fn();
    render(
      <IntroOptionSetDocument
        canSelect
        content={content}
        onSelect={onSelect}
        selectedOptionKey="INTRO-SCI-01"
      />,
    );

    const firstAdoptButton = screen.getAllByRole("button", { name: "采用本方案" }).at(0);
    if (!firstAdoptButton) throw new Error("No adoptable Intro option was rendered.");
    fireEvent.click(firstAdoptButton);
    expect(onSelect).toHaveBeenCalledWith("INTRO-SCI-02");
  });
});
