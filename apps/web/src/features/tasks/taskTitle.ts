import { getNodeDef } from "@/entities/workflow/nodes";

const TASK_TYPE_LABEL: Record<string, string> = {
  textbook_parse: "教材解析",
  lesson_division_generate: "课时划分生成",
  delivery_package: "交付打包",
  provider_connection_test: "模型服务连通性测试",
  template_dry_run: "Prompt模板试运行",
  clip_retry: "镜头片段重试",
  image_retry: "图片资产重试",
  anchor_redo: "课程锚点重出",
};

/** 任务的教师可读名称（后端只给 task_type + node_key）。 */
export function taskTitle(task: { task_type: string; node_key?: string | null }): string {
  if (task.task_type.startsWith("node_run:")) {
    const key = task.task_type.slice("node_run:".length);
    return `${getNodeDef(key)?.title ?? key}生成`;
  }
  if (task.task_type.startsWith("item_revise:")) {
    const key = task.task_type.slice("item_revise:".length);
    return `${getNodeDef(key)?.title ?? key}局部修订`;
  }
  return TASK_TYPE_LABEL[task.task_type] ?? task.task_type;
}
