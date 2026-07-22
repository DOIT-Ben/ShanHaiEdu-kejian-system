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
    viewport: {
      options: {
        desktop1440: { name: "Desktop 1440", styles: { height: "900px", width: "1440px" } },
        desktop1280: { name: "Desktop 1280", styles: { height: "800px", width: "1280px" } },
        tablet1024: { name: "Tablet 1024", styles: { height: "768px", width: "1024px" } },
        narrow390: { name: "Narrow 390", styles: { height: "844px", width: "390px" } },
      },
    },
  },
  tags: ["autodocs"],
};

export default preview;
