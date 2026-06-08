import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

// A REAL terminal in the SPA, wired to the backend PTY at /ws/terminal. This is the LOGIN surface:
// the user runs `claude auth login` here and does the browser OAuth on their OWN subscription, so
// no creds are copied or baked. Bytes round-trip: term.onData -> ws (keystrokes); ws.onmessage ->
// term.write (PTY output); term.onResize -> a JSON control frame the backend turns into TIOCSWINSZ.
export function TerminalPanel() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;

    const term = new Terminal({
      convertEol: true,
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
      theme: { background: "#0b0e14", foreground: "#cdd6f4" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(host);
    const safeFit = () => {
      try {
        fit.fit();
      } catch {
        /* not visible yet */
      }
    };
    safeFit();

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/terminal`);

    ws.onopen = () => {
      safeFit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    };
    ws.onmessage = (e: MessageEvent) => {
      if (typeof e.data === "string") term.write(e.data);
    };
    ws.onclose = () => term.write("\r\n\x1b[33m[terminal disconnected — reload to reconnect]\x1b[0m\r\n");

    const dataSub = term.onData((d) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(d);
    });
    const resizeSub = term.onResize(({ cols, rows }) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "resize", cols, rows }));
    });
    const onWinResize = () => safeFit();
    window.addEventListener("resize", onWinResize);

    return () => {
      window.removeEventListener("resize", onWinResize);
      dataSub.dispose();
      resizeSub.dispose();
      try {
        ws.close();
      } catch {
        /* ignore */
      }
      term.dispose();
    };
  }, []);

  return <div className="terminal-host" ref={ref} />;
}
