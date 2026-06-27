"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Service, ServiceState, WsMessage } from "@/types/lookout";

const RECONNECT_DELAY_MS = 3000;

type BadgeVariant = "up" | "warning" | "critical" | "unknown";

function stateVariant(state: ServiceState): BadgeVariant {
  switch (state) {
    case "UP":
    case "RESOLVED":
      return "up";
    case "WARNING":
      return "warning";
    case "CRITICAL":
    case "DOWN":
      return "critical";
    default:
      return "unknown";
  }
}

function stateLabel(state: ServiceState): string {
  return state;
}

function buildWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/v1/dashboard`;
}

export function Dashboard() {
  const [services, setServices] = useState<Map<string, Service>>(new Map());
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const addEvent = (msg: string) =>
    setEvents((prev) => [msg, ...prev].slice(0, 50));

  useEffect(() => {
    let alive = true;

    function connect() {
      if (!alive) return;
      const ws = new WebSocket(buildWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        addEvent("Connected to Lookout backend");
      };

      ws.onmessage = (ev) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(ev.data as string) as WsMessage;
        } catch {
          return;
        }

        if (msg.type === "snapshot") {
          setServices(new Map(msg.services.map((s) => [s.id, s])));
          addEvent(`Snapshot received — ${msg.services.length} services`);
        } else if (msg.type === "state_change") {
          setServices((prev) => {
            const next = new Map(prev);
            const svc = next.get(msg.service_id);
            if (svc) next.set(msg.service_id, { ...svc, current_state: msg.new_state });
            return next;
          });
          addEvent(
            `${msg.service_name}: ${msg.previous_state ?? "?"} → ${msg.new_state}`
          );
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (alive) {
          addEvent(`Disconnected — retrying in ${RECONNECT_DELAY_MS / 1000}s`);
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      alive = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  const serviceList = Array.from(services.values());

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] p-6">
      {/* Header */}
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-widest text-[hsl(var(--primary))] uppercase">
            Lookout
          </h1>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-0.5 tracking-wider">
            Infrastructure HUD
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              connected ? "bg-green-400 shadow-[0_0_8px_#4ade80]" : "bg-red-500"
            }`}
          />
          <span className="text-xs text-[hsl(var(--muted-foreground))]">
            {connected ? "LIVE" : "RECONNECTING"}
          </span>
        </div>
      </header>

      {/* Service Grid */}
      {serviceList.length === 0 ? (
        <div className="flex items-center justify-center h-48 text-[hsl(var(--muted-foreground))] text-sm tracking-widest">
          {connected ? "AWAITING SERVICES..." : "CONNECTING..."}
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 mb-8">
          {serviceList.map((svc) => {
            const variant = stateVariant(svc.current_state);
            return (
              <Card
                key={svc.id}
                className={`border transition-colors duration-500 ${
                  variant === "critical"
                    ? "border-red-500/30 shadow-[0_0_12px_rgba(239,68,68,0.15)]"
                    : variant === "up"
                    ? "border-green-500/20"
                    : variant === "warning"
                    ? "border-yellow-500/20"
                    : "border-[hsl(var(--border))]"
                }`}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-sm font-mono truncate">
                      {svc.name}
                    </CardTitle>
                    <Badge variant={variant}>{stateLabel(svc.current_state)}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1 text-xs text-[hsl(var(--muted-foreground))]">
                    <div className="flex justify-between">
                      <span>TYPE</span>
                      <span className="uppercase tracking-widest">{svc.type}</span>
                    </div>
                    {svc.target && (
                      <div className="flex justify-between">
                        <span>TARGET</span>
                        <span className="truncate max-w-[120px] text-right" title={svc.target}>
                          {svc.target}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span>INTERVAL</span>
                      <span>{svc.interval_s}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span>STATUS</span>
                      <span>{svc.enabled ? "ENABLED" : "DISABLED"}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Event log */}
      <section>
        <h2 className="text-xs font-semibold tracking-[0.2em] text-[hsl(var(--muted-foreground))] uppercase mb-3">
          Event Log
        </h2>
        <Card className="border-[hsl(var(--border))]">
          <ScrollArea className="h-48 p-3">
            {events.length === 0 ? (
              <p className="text-xs text-[hsl(var(--muted-foreground))]">No events yet.</p>
            ) : (
              <ul className="space-y-1">
                {events.map((e, i) => (
                  <li key={i} className="text-xs font-mono text-[hsl(var(--muted-foreground))]">
                    <span className="text-[hsl(var(--primary))] mr-2">›</span>
                    {e}
                  </li>
                ))}
              </ul>
            )}
          </ScrollArea>
        </Card>
      </section>
    </div>
  );
}
