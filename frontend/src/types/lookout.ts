export type ServiceState =
  | "UNKNOWN"
  | "UP"
  | "DOWN"
  | "WARNING"
  | "CRITICAL"
  | "RESOLVED";

export interface Service {
  id: string;
  name: string;
  type: "http" | "tcp" | "push";
  target: string | null;
  current_state: ServiceState;
  interval_s: number;
  enabled: boolean;
}

export interface SnapshotMessage {
  type: "snapshot";
  services: Service[];
}

export interface StateChangeMessage {
  type: "state_change";
  service_id: string;
  service_name: string;
  new_state: ServiceState;
  previous_state?: ServiceState;
  fired_at?: string;
  resolved_at?: string;
  changed_at?: string;
}

export interface PingMessage {
  type: "ping";
}

export type WsMessage = SnapshotMessage | StateChangeMessage | PingMessage;
