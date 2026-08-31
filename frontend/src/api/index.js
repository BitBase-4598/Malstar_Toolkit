import { remarksApi, RECORDS_PAGE_SIZE } from "./remarks";
import { filesApi } from "./files";
import { sopsApi } from "./sops";
import { leaveApi } from "./leave";
import { logsApi } from "./logs";
import { askApi } from "./ask";
import { dashboardApi } from "./dashboard";
import { lclApi } from "./lcl";
import { icbApi } from "./icb";
import { unlocoApi } from "./unloco";
import { gcaApi } from "./gca";
import { casesApi } from "./cases";

export { RECORDS_PAGE_SIZE };

export const api = {
  ...remarksApi,
  ...filesApi,
  ...sopsApi,
  ...leaveApi,
  ...logsApi,
  ...askApi,
  ...dashboardApi,
  ...lclApi,
  ...icbApi,
  ...unlocoApi,
  ...gcaApi,
  ...casesApi,
};
