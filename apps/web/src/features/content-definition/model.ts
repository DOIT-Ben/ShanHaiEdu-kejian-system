export type ContentField = {
  field_key: string;
  label: string;
  description?: string;
  type: string;
  required: boolean;
  editable: boolean;
  deletable: boolean;
  children?: ContentField[];
};

export type ContentDefinition = {
  definition_key: string;
  title: string;
  description?: string;
  fields: ContentField[];
};

export type ContentData = Record<string, unknown>;
