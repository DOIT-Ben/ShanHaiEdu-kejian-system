import type { Preview } from "@storybook/react-vite";
import { MemoryRouter } from "react-router-dom";
import { AppProviders } from "../src/app/providers/AppProviders";
import "../src/shared/styles/index.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <MemoryRouter>
        <AppProviders>
          <div className="min-h-screen bg-[var(--sh-surface-canvas)] p-6">
            <Story />
          </div>
        </AppProviders>
      </MemoryRouter>
    ),
  ],
  parameters: {
    controls: { expanded: true },
    a11y: { test: "error" },
    backgrounds: { disable: true },
    layout: "fullscreen",
  },
  tags: ["autodocs"],
};

export default preview;
