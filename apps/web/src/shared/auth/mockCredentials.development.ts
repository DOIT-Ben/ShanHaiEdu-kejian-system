import type { MockRole } from "@/shared/api/mocks/runtime";

export type DevelopmentMockAccount = {
  email: string;
  password: string;
  name: string;
};

export const developmentMockAccounts: Record<MockRole, DevelopmentMockAccount> = {
  teacher: {
    email: "lin.teacher@example.edu",
    password: "teacher-demo",
    name: "林老师",
  },
  admin: {
    email: "admin@example.edu",
    password: "admin-demo",
    name: "山海管理员",
  },
};
