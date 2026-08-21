function pad(value) {
  return String(value).padStart(2, "0");
}

function toIso(year, monthIndex, day) {
  return `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
}

function isoRange(start, end) {
  const dates = [];
  const cursor = new Date(`${start}T00:00:00`);
  const last = new Date(`${end}T00:00:00`);
  while (cursor <= last) {
    dates.push(toIso(cursor.getFullYear(), cursor.getMonth(), cursor.getDate()));
    cursor.setDate(cursor.getDate() + 1);
  }
  return dates;
}

const YEAR_CALENDARS = {
  2026: {
    holidays: [
      ["2026-01-01", "2026-01-03", "元旦", "New Year", "元旦"],
      ["2026-02-15", "2026-02-23", "春节", "Spring Festival", "春节"],
      ["2026-04-04", "2026-04-06", "清明节", "Qingming Festival", "清明"],
      ["2026-05-01", "2026-05-05", "劳动节", "Labour Day", "劳动"],
      ["2026-06-19", "2026-06-21", "端午节", "Dragon Boat Festival", "端午"],
      ["2026-09-25", "2026-09-27", "中秋节", "Mid-Autumn Festival", "中秋"],
      ["2026-10-01", "2026-10-07", "国庆节", "National Day", "国庆"],
    ],
    makeupWorkdays: ["2026-01-04", "2026-02-14", "2026-02-28", "2026-05-09", "2026-09-20", "2026-10-10"],
  },
};

const cache = new Map();

function calendarForYear(year) {
  if (cache.has(year)) {
    return cache.get(year);
  }
  const source = YEAR_CALENDARS[year] || { holidays: [], makeupWorkdays: [] };
  const holidays = new Map();
  source.holidays.forEach(([start, end, nameZh, nameEn, shortLabel]) => {
    isoRange(start, end).forEach((iso) => {
      holidays.set(iso, { nameZh, nameEn, shortLabel });
    });
  });
  const makeupWorkdays = new Set(source.makeupWorkdays);
  const packed = { holidays, makeupWorkdays };
  cache.set(year, packed);
  return packed;
}

export function holidayInfo(iso) {
  const year = Number(String(iso || "").slice(0, 4));
  if (!year) {
    return null;
  }
  return calendarForYear(year).holidays.get(iso) || null;
}

export function isPublicHoliday(iso) {
  return Boolean(holidayInfo(iso));
}

export function isWeekend(iso) {
  const weekday = new Date(`${iso}T00:00:00`).getDay();
  return weekday === 0 || weekday === 6;
}

export function isOffDay(iso) {
  const year = Number(String(iso || "").slice(0, 4));
  if (year && calendarForYear(year).makeupWorkdays.has(iso)) {
    return false;
  }
  return isWeekend(iso) || isPublicHoliday(iso);
}
