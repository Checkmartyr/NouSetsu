import React, { useState, useEffect, useCallback, useRef, useSyncExternalStore } from 'react';
import {
  CheckCircle2, AlertCircle, Loader2, Clock, Server, BookOpen,
  Radio, Cpu, Layers, RefreshCw, ShieldAlert,
} from 'lucide-react';
import {
  type ServiceCheckId,
  type StartupData,
  getStartupSnapshot,
  subscribeStartup,
  startVerification,
} from '../services/serviceChecker';

interface StartupLoadingScreenProps {
  onReady: (data: StartupData) => void;
}

const CHECK_ICONS: Record<ServiceCheckId, React.ComponentType<{ className?: string }>> = {
  backend: Server,
  project: BookOpen,
  events: Radio,
  models: Cpu,
  chapters: Layers,
};

export const StartupLoadingScreen: React.FC<StartupLoadingScreenProps> = ({ onReady }) => {
  const snapshot = useSyncExternalStore(subscribeStartup, getStartupSnapshot);
  const { checks, progress, message: statusMessage, error: diagnosticDetails } = snapshot;
  const hasFatalError = snapshot.status === 'error';
  const [isFadingOut, setIsFadingOut] = useState(false);
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;
  const transitionTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTransitionTimers = useCallback(() => {
    transitionTimers.current.forEach(clearTimeout);
    transitionTimers.current = [];
  }, []);

  useEffect(() => {
    void startVerification();
    return clearTransitionTimers;
  }, [clearTransitionTimers]);

  useEffect(() => {
    if (snapshot.status !== 'ready') return;
    transitionTimers.current.push(setTimeout(() => {
      setIsFadingOut(true);
      transitionTimers.current.push(setTimeout(() => {
        onReadyRef.current(snapshot.data);
      }, snapshot.lightweight ? 0 : 400));
    }, snapshot.lightweight ? 0 : 500));
    return clearTransitionTimers;
  }, [snapshot.status, snapshot.data, snapshot.lightweight, clearTransitionTimers]);

  const runVerification = () => {
    clearTransitionTimers();
    setIsFadingOut(false);
    void startVerification(true);
  };

  const handleBypass = () => {
    clearTransitionTimers();
    setIsFadingOut(true);
    transitionTimers.current.push(setTimeout(() => {
      onReadyRef.current(snapshot.data);
    }, 300));
  };

  if (snapshot.lightweight && !hasFatalError) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#2b2622] text-[#f7f5f0]" role="status">
        <Loader2 className="w-5 h-5 animate-spin mr-3" />
        <span>Connecting to novel workspace...</span>
      </div>
    );
  }

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#2b2622] text-[#f7f5f0] p-4 sm:p-6 transition-opacity duration-400 select-none ${
        isFadingOut ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
    >
      <div className="w-full max-w-lg bg-[#383330] border border-[#3f3a36] rounded-[6px] shadow-2xl overflow-hidden animate-fade-in flex flex-col">
        {/* Header / Brand Crest */}
        <div className="p-6 pb-4 border-b border-[#3f3a36] flex flex-col items-center text-center bg-gradient-to-b from-[#423c37]/50 to-transparent">
          <div className="relative mb-3 flex items-center justify-center">
            <div className="w-14 h-14 rounded-[8px] bg-[#2b2622] border border-[#544d47] flex items-center justify-center overflow-hidden shadow-inner p-1">
              <img
                src="/logo.png?v=story-portal-1"
                alt="Nousetsu"
                className="w-full h-full object-contain rounded-[4px]"
              />
            </div>
            <span className="absolute -bottom-1 -right-1 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500 border-2 border-[#383330]"></span>
            </span>
          </div>

          <div className="flex items-center gap-2">
            <h1 className="text-xl font-medium tracking-tight text-[#f7f5f0]">Nousetsu</h1>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-[2px] bg-[#2b2622] text-[#dad2c1] border border-[#3f3a36]">
              desktop studio
            </span>
          </div>
          <p className="text-xs text-[#aea69c] mt-0.5 font-sans">
            Literary Novel Translation & Chapter Intelligence
          </p>

          <div className="mt-2.5 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#2b2622] border border-[#3f3a36] text-[11px] font-mono text-[#dad2c1]">
            <span>(=^･ω･^=)</span>
            <span>Verifying service readiness...</span>
          </div>
        </div>

        {/* Progress Bar Ribbon */}
        <div className="w-full bg-[#24201d] h-1.5 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[#aea69c] via-[#dad2c1] to-emerald-400 transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Checklist Body */}
        <div className="p-5 space-y-2.5 flex-1">
          {checks.map((item) => {
            const Icon = CHECK_ICONS[item.id] || Server;
            return (
              <div
                key={item.id}
                className={`flex items-center justify-between p-2.5 rounded-[4px] border transition-colors ${
                  item.status === 'ready'
                    ? 'bg-[#2b2622]/60 border-[#3f3a36]'
                    : item.status === 'checking'
                    ? 'bg-[#453f3a]/80 border-[#544d47]'
                    : item.status === 'error'
                    ? 'bg-rose-950/40 border-rose-900/60'
                    : 'bg-[#2b2622]/30 border-[#383330] opacity-60'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`w-7 h-7 rounded-[4px] flex items-center justify-center shrink-0 border ${
                      item.status === 'ready'
                        ? 'bg-emerald-950/40 border-emerald-800/40 text-emerald-400'
                        : item.status === 'checking'
                        ? 'bg-amber-950/40 border-amber-800/40 text-amber-300'
                        : item.status === 'error'
                        ? 'bg-rose-950/40 border-rose-800/40 text-rose-400'
                        : 'bg-[#2b2622] border-[#3f3a36] text-[#aea69c]'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>

                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-[#f7f5f0] truncate">
                        {item.label}
                      </span>
                      {item.latencyMs !== undefined && (
                        <span className="text-[10px] font-mono text-[#aea69c]">
                          {item.latencyMs}ms
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-[#aea69c] truncate font-sans">
                      {item.error || item.description}
                    </p>
                  </div>
                </div>

                <div className="shrink-0 ml-3">
                  {item.status === 'ready' && (
                    <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-mono">
                      <CheckCircle2 className="w-4 h-4" />
                      <span className="hidden sm:inline">READY</span>
                    </span>
                  )}
                  {item.status === 'checking' && (
                    <span className="flex items-center gap-1 text-[11px] text-amber-300 font-mono">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="hidden sm:inline">CHECKING</span>
                    </span>
                  )}
                  {item.status === 'pending' && (
                    <Clock className="w-4 h-4 text-[#aea69c]/50" />
                  )}
                  {item.status === 'error' && (
                    <span className="flex items-center gap-1 text-[11px] text-rose-400 font-mono">
                      <AlertCircle className="w-4 h-4" />
                      <span className="hidden sm:inline">ERROR</span>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Diagnostic / Error Actions if stuck */}
        {hasFatalError && (
          <div className="px-5 py-3 bg-rose-950/30 border-t border-rose-900/50 flex flex-col gap-2">
            <div className="flex items-start gap-2 text-rose-300 text-xs">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <div>
                <p className="font-medium">Service Initialization Stalled</p>
                <p className="text-[11px] text-rose-200/80 mt-0.5">
                  {diagnosticDetails ||
                    'A required service did not respond. Check if another process is holding port 15474.'}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 mt-1">
              <button
                type="button"
                onClick={handleBypass}
                className="px-2.5 py-1 text-xs text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer transition-colors"
                title="Continue anyway in degraded mode"
              >
                Skip & Continue
              </button>
              <button
                type="button"
                onClick={runVerification}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#453f3a] hover:bg-[#544d47] text-[#f7f5f0] border border-[#544d47] rounded-[3px] text-xs font-medium cursor-pointer transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Verification</span>
              </button>
            </div>
          </div>
        )}

        {/* Footer Status Bar */}
        <div className="px-5 py-3 border-t border-[#3f3a36] bg-[#2b2622] flex items-center justify-between text-[11px] font-mono text-[#aea69c]">
          <div className="flex items-center gap-2 truncate">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0"></span>
            <span className="truncate">{statusMessage}</span>
          </div>
          <span className="shrink-0 text-[#dad2c1] ml-2">{progress}%</span>
        </div>
      </div>
    </div>
  );
};
