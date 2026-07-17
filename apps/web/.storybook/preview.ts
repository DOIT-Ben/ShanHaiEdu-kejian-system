import type { Preview } from "@storybook/react";
import React from "react";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "../src/shared/ui/tooltip";
import "../src/shared/styles/globals.css";

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: "page",
      values: [
        { name: "page", value: "#F6F7FA" },
        { name: "surface", value: "#FFFFFF" },
      ],
    },
    controls: { expanded: true },
  },
  decorators: [
    (Story) =>
      React.createElement(
        QueryClientProvider,
        { client: new QueryClient({ defaultOptions: { queries: { retry: false } } }) },
        React.createElement(
          MemoryRouter,
          null,
          React.createElement(TooltipProvider, { delayDuration: 200 }, React.createElement(Story)),
        ),
      ),
  ],
};

export default preview;
