import { useMemo, useState } from "react";
import { PencilLine } from "lucide-react";
import { lessonPlanContentSchema, parseContent, type LessonPlanContent } from "@/entities/content";
import { Button, Textarea } from "@/shared/ui";
import type { CanvasProps } from "../registry";
import { InvalidContent } from "./invalid-content";

/**
 * 教案画布：12 固定环节；支持分环节直接编辑，保存为新版本；
 * 「教学过程」环节以阶段表呈现。
 */
export function LessonPlanCanvas({ workspace, onSaveEdited, savePending }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(lessonPlanContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draftBody, setDraftBody] = useState("");

  if (!content) return <InvalidContent nodeTitle="教案" />;

  const saveSection = (sectionKey: string) => {
    const next: LessonPlanContent = {
      ...content,
      sections: content.sections.map((section) =>
        section.key === sectionKey ? { ...section, body: draftBody } : section,
      ),
    };
    onSaveEdited(next as unknown as Record<string, unknown>);
    setEditingKey(null);
  };

  return (
    <article className="space-y-5">
      <h2 className="text-lg font-semibold text-ink-1">{content.lesson_title}</h2>
      {content.sections.map((section, index) => (
        <section key={section.key} className="group">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-ink-1">
              {index + 1}. {section.title}
            </h3>
            {section.kind === "text" && editingKey !== section.key ? (
              <Button
                size="sm"
                variant="ghost"
                className="opacity-0 transition-opacity group-hover:opacity-100"
                onClick={() => {
                  setEditingKey(section.key);
                  setDraftBody(section.body);
                }}
              >
                <PencilLine className="size-3.5" aria-hidden />
                编辑
              </Button>
            ) : null}
          </div>
          {section.kind === "process" ? (
            <table className="mt-2 w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-muted">
                  <th className="py-1.5 pr-3 font-medium">阶段</th>
                  <th className="py-1.5 pr-3 font-medium">时长</th>
                  <th className="py-1.5 pr-3 font-medium">教师活动</th>
                  <th className="py-1.5 pr-3 font-medium">学生活动</th>
                  <th className="py-1.5 font-medium">设计意图</th>
                </tr>
              </thead>
              <tbody>
                {section.stages.map((stage) => (
                  <tr key={stage.stage_id} className="border-b border-divider align-top">
                    <td className="py-2 pr-3 font-medium text-ink-1">{stage.stage_title}</td>
                    <td className="py-2 pr-3 whitespace-nowrap text-ink-2">{stage.minutes} 分钟</td>
                    <td className="py-2 pr-3 leading-6 text-ink-2">{stage.teacher_activity}</td>
                    <td className="py-2 pr-3 leading-6 text-ink-2">{stage.student_activity}</td>
                    <td className="py-2 leading-6 text-ink-muted">{stage.design_intent}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : editingKey === section.key ? (
            <div className="mt-2 space-y-2">
              <Textarea
                rows={5}
                value={draftBody}
                onChange={(event) => setDraftBody(event.target.value)}
                aria-label={`编辑「${section.title}」`}
              />
              <div className="flex justify-end gap-2">
                <Button size="sm" variant="ghost" onClick={() => setEditingKey(null)}>
                  取消
                </Button>
                <Button size="sm" loading={savePending} onClick={() => saveSection(section.key)}>
                  保存为新版本
                </Button>
              </div>
            </div>
          ) : (
            <p className="mt-1.5 whitespace-pre-wrap text-sm leading-7 text-ink-2">{section.body || "（未填写）"}</p>
          )}
        </section>
      ))}
    </article>
  );
}
