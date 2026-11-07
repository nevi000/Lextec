import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

// Pages are lazy-loaded; the first import of a large page can exceed the 1s default under load.
configure({ asyncUtilTimeout: 5000 });
