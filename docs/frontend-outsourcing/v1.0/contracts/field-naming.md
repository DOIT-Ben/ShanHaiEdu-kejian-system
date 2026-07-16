# 字段命名规范

## JSON和OpenAPI

- 对外API字段使用`snake_case`，与FastAPI后端保持一致。
- TypeScript生成类型不得手工改名。
- React组件Props使用`camelCase`。
- 业务ID使用明确前缀字段，如`project_id`、`lesson_id`、`artifact_version_id`。
- 不使用含义不清的`id`、`data1`、`value2`。

## 状态

状态使用稳定英文枚举，教师文案由前端映射。前端不得把中文文案反向作为状态判断。

## 时间

- API时间为UTC ISO 8601。
- 前端根据用户时区显示。
- 字段以`_at`结尾。

## 金额

- 使用`*_minor_units`整数或后端返回的格式化字符串。
- 前端不得使用浮点执行正式费用加总。

## 版本

- `row_version`用于乐观锁。
- `version_number`是产物内展示序号。
- `*_version_id`是不可变版本引用。

## 文件

- 文件元数据使用`file_object_id`。
- 前端只使用后端授权的`preview_url`和下载授权。
- 不保存私有对象存储路径作为公开URL。

