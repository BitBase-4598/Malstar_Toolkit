import { remarksApi, RECORDS_PAGE_SIZE } from "./remarks";
import { filesApi } from "./files";
import { sopsApi } from "./sops";
import { leaveApi } from "./leave";
import { logsApi } from "./logs";
import { askApi } from "./ask";
import { dashboardApi } from "./dashboard";

export { RECORDS_PAGE_SIZE };

export const api = {
  ...remarksApi,
  ...filesApi,
  ...sopsApi,
  ...leaveApi,
  ...logsApi,
  ...askApi,
  ...dashboardApi,
};
