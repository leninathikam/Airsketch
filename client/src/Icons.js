const paths = {
  plus: <path d="M12 5v14M5 12h14" />,
  camera: <><rect x="3" y="6" width="12" height="12" rx="2" /><path d="m15 10 6-3v10l-6-3" /></>,
  mic: <><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M9 22h6" /></>,
  stop: <rect x="6" y="6" width="12" height="12" rx="1" />,
  expand: <path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5" />,
  collapse: <path d="M3 8h5V3M21 8h-5V3M16 21v-5h5M8 21v-5H3" />,
  erase: <><path d="m14 3 7 7-10 10H7l-5-5L14 3ZM7 10l8 8M11 20h10" /></>,
  undo: <><path d="M3 9h11a6 6 0 0 1 0 12h-3M3 9l5-5M3 9l5 5" /></>,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
  copy: <><rect x="8" y="8" width="12" height="13" rx="2" /><path d="M15 8V3H3v13h5" /></>,
  search: <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  up: <path d="m6 15 6-6 6 6" />,
  down: <path d="m6 9 6 6 6-6" />,
  document: <><path d="M6 3h8l4 4v14H6V3Zm8 0v5h4M9 12h6M9 16h6" /></>,
  note: <><path d="M4 4h16v12l-4 4H4V4Zm12 16v-4h4M8 8h8M8 12h5" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  photo: <><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8" cy="8" r="1.5" /><path d="m3 17 6-6 4 4 3-3 5 5" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3M12 17h.01" /></>,
};
export default function Icon({ name, size = 18, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}
