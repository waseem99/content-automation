import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type {CaptionChunk, StoryScene, VideoInputProps} from "./types";

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

const highlightColors: Record<string, string> = {
  neutral: "#FFFFFF",
  danger: "#FF5B62",
  positive: "#65E7A2",
  fact: "#FFD84D",
};

const Ant: React.FC<{
  x: number;
  y: number;
  scale?: number;
  rotation?: number;
  opacity?: number;
  color?: string;
}> = ({x, y, scale = 1, rotation = 0, opacity = 1, color = "#111827"}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: 74,
      height: 28,
      transform: `rotate(${rotation}deg) scale(${scale})`,
      transformOrigin: "center",
      opacity,
    }}
  >
    {[0, 25, 50].map((offset, index) => (
      <div
        key={offset}
        style={{
          position: "absolute",
          left: offset,
          top: index === 1 ? 1 : 4,
          width: index === 1 ? 28 : 24,
          height: index === 1 ? 26 : 20,
          borderRadius: "50%",
          background: color,
          boxShadow: "0 8px 18px rgba(0,0,0,.2)",
        }}
      />
    ))}
    {[7, 27, 47].map((offset) => (
      <React.Fragment key={offset}>
        <div
          style={{
            position: "absolute",
            left: offset,
            top: -7,
            width: 36,
            height: 3,
            borderRadius: 999,
            background: color,
            transform: "rotate(-28deg)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: offset,
            top: 29,
            width: 36,
            height: 3,
            borderRadius: 999,
            background: color,
            transform: "rotate(28deg)",
          }}
        />
      </React.Fragment>
    ))}
  </div>
);

const Background: React.FC<{accent: string; progress: number}> = ({accent, progress}) => {
  const drift = interpolate(progress, [0, 1], [-60, 90]);
  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        background:
          "radial-gradient(circle at 22% 12%, rgba(255,255,255,.22), transparent 26%), linear-gradient(165deg, #0A101B 0%, #182431 52%, #0B1018 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 920,
          height: 920,
          borderRadius: "50%",
          left: -420 + drift,
          top: 210,
          background: accent,
          opacity: 0.16,
          filter: "blur(12px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 720,
          height: 720,
          borderRadius: "50%",
          right: -360 - drift,
          bottom: 130,
          border: `4px solid ${accent}`,
          opacity: 0.15,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.08,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.16) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.16) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
        }}
      />
    </AbsoluteFill>
  );
};

const SwarmVisual: React.FC<{frame: number; accent: string}> = ({frame, accent}) => (
  <div style={{position: "absolute", inset: 0}}>
    {Array.from({length: 18}).map((_, index) => {
      const lane = index % 6;
      const row = Math.floor(index / 6);
      const x = ((frame * (2.4 + row * 0.5) + index * 173) % 1280) - 160;
      const y = 620 + lane * 105 + Math.sin((frame + index * 21) / 18) * 38;
      return (
        <Ant
          key={index}
          x={x}
          y={y}
          scale={0.68 + row * 0.1}
          rotation={Math.sin((frame + index) / 24) * 8}
          color={index % 5 === 0 ? accent : "#141A22"}
        />
      );
    })}
  </div>
);

const BridgeVisual: React.FC<{frame: number; accent: string; traffic: boolean}> = ({
  frame,
  accent,
  traffic,
}) => {
  const pulse = 1 + Math.sin(frame / 12) * 0.025;
  return (
    <div style={{position: "absolute", inset: 0}}>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 915,
          width: 340,
          height: 420,
          background: "linear-gradient(90deg, #263C31, #17251E)",
          borderRadius: "0 110px 110px 0",
          boxShadow: "0 30px 80px rgba(0,0,0,.35)",
        }}
      />
      <div
        style={{
          position: "absolute",
          right: 0,
          top: 880,
          width: 340,
          height: 460,
          background: "linear-gradient(270deg, #263C31, #17251E)",
          borderRadius: "110px 0 0 110px",
          boxShadow: "0 30px 80px rgba(0,0,0,.35)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 260,
          right: 260,
          top: 1035,
          height: 120,
          transform: `scale(${pulse}) rotate(-2deg)`,
          transformOrigin: "center",
        }}
      >
        {Array.from({length: 11}).map((_, index) => (
          <Ant
            key={index}
            x={index * 55}
            y={Math.sin(index * 0.75) * 18}
            scale={0.62}
            rotation={index % 2 === 0 ? 6 : -6}
            color={index === 5 ? accent : "#10161D"}
          />
        ))}
      </div>
      {traffic &&
        Array.from({length: 6}).map((_, index) => {
          const x = ((frame * 5 + index * 210) % 980) + 50;
          return (
            <Ant
              key={`traffic-${index}`}
              x={x}
              y={960 + Math.sin((frame + index * 20) / 16) * 12}
              scale={0.52}
              color={accent}
            />
          );
        })}
    </div>
  );
};

const HookVisual: React.FC<{frame: number; accent: string}> = ({frame, accent}) => {
  const zoom = interpolate(frame, [0, 55], [0.72, 1.08], clamp);
  const rotate = interpolate(frame, [0, 55], [-8, 2], clamp);
  return (
    <div
      style={{
        position: "absolute",
        left: 190,
        top: 530,
        width: 700,
        height: 700,
        transform: `scale(${zoom}) rotate(${rotate}deg)`,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 70,
          borderRadius: 90,
          border: `18px solid ${accent}`,
          boxShadow: `0 0 90px ${accent}66`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 120,
          right: 120,
          top: 315,
          height: 82,
          borderRadius: 999,
          background: "#0A101B",
          transform: "rotate(-4deg)",
        }}
      />
      {Array.from({length: 7}).map((_, index) => (
        <Ant
          key={index}
          x={110 + index * 74}
          y={300 + Math.sin((frame + index * 8) / 12) * 20}
          scale={0.56}
          rotation={index % 2 ? -5 : 6}
          color={index === 3 ? accent : "#151D27"}
        />
      ))}
    </div>
  );
};

const RevealVisual: React.FC<{frame: number; accent: string}> = ({frame, accent}) => {
  const entry = spring({frame, fps: 30, config: {damping: 16, stiffness: 130}});
  return (
    <div
      style={{
        position: "absolute",
        left: 120,
        right: 120,
        top: 610,
        display: "grid",
        gap: 32,
        transform: `translateY(${interpolate(entry, [0, 1], [120, 0])}px)`,
        opacity: entry,
      }}
    >
      {["BUILD", "CROSS", "DISASSEMBLE"].map((label, index) => (
        <div
          key={label}
          style={{
            minHeight: 170,
            padding: "34px 42px",
            borderRadius: 40,
            background: index === 1 ? accent : "rgba(255,255,255,.08)",
            border: "2px solid rgba(255,255,255,.15)",
            color: index === 1 ? "#10161D" : "#FFFFFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: 46,
            fontWeight: 900,
            letterSpacing: ".04em",
          }}
        >
          <span>{String(index + 1).padStart(2, "0")}</span>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
};

const CtaVisual: React.FC<{frame: number; accent: string; cta: string}> = ({
  frame,
  accent,
  cta,
}) => {
  const pop = spring({frame, fps: 30, config: {damping: 14, stiffness: 120}});
  return (
    <div
      style={{
        position: "absolute",
        left: 100,
        right: 100,
        top: 570,
        padding: "80px 60px",
        borderRadius: 62,
        background: "rgba(255,255,255,.96)",
        color: "#0B1018",
        textAlign: "center",
        transform: `scale(${interpolate(pop, [0, 1], [0.75, 1])})`,
        opacity: pop,
        boxShadow: "0 42px 110px rgba(0,0,0,.4)",
      }}
    >
      <div style={{fontSize: 40, fontWeight: 900, color: accent, letterSpacing: ".12em"}}>
        RAWR NATION
      </div>
      <div style={{fontSize: 76, fontWeight: 950, lineHeight: 1.02, marginTop: 34}}>{cta}</div>
      <div style={{fontSize: 30, color: "#4B5563", marginTop: 30}}>Verified facts. Simple explanations.</div>
    </div>
  );
};

const VisualStage: React.FC<{scene: StoryScene; localFrame: number}> = ({scene, localFrame}) => {
  const accent = scene.accent ?? "#FFD84D";
  if (scene.visual === "hook") return <HookVisual frame={localFrame} accent={accent} />;
  if (scene.visual === "swarm") return <SwarmVisual frame={localFrame} accent={accent} />;
  if (scene.visual === "bridge") return <BridgeVisual frame={localFrame} accent={accent} traffic={false} />;
  if (scene.visual === "traffic") return <BridgeVisual frame={localFrame} accent={accent} traffic />;
  if (scene.visual === "reveal") return <RevealVisual frame={localFrame} accent={accent} />;
  return <CtaVisual frame={localFrame} accent={accent} cta={scene.body} />;
};

const Caption: React.FC<{caption?: CaptionChunk}> = ({caption}) => {
  if (!caption) return null;
  const words = caption.text.split(/\s+/);
  const target = caption.highlight?.toLowerCase();
  const color = highlightColors[caption.emphasis ?? "neutral"];
  return (
    <div
      style={{
        position: "absolute",
        left: 70,
        right: 70,
        bottom: 240,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "4px 18px",
        textAlign: "center",
        fontSize: 68,
        lineHeight: 1.04,
        fontWeight: 950,
        letterSpacing: "-.035em",
        color: "#FFFFFF",
        textTransform: "uppercase",
        textShadow: "0 7px 0 #000, 0 0 24px rgba(0,0,0,.8)",
      }}
    >
      {words.map((word, index) => {
        const normalized = word.replace(/[^a-z0-9]/gi, "").toLowerCase();
        const highlighted = target && normalized === target.replace(/[^a-z0-9]/gi, "");
        return (
          <span key={`${word}-${index}`} style={{color: highlighted ? color : "#FFFFFF"}}>
            {word}
          </span>
        );
      })}
    </div>
  );
};

export const RawrNationShort: React.FC<VideoInputProps> = ({project}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const seconds = frame / fps;
  const scene =
    project.scenes.find((item) => seconds >= item.startSec && seconds < item.endSec) ??
    project.scenes[project.scenes.length - 1];
  const localFrame = Math.max(0, frame - Math.round(scene.startSec * fps));
  const sceneDuration = Math.max(1, (scene.endSec - scene.startSec) * fps);
  const enter = interpolate(localFrame, [0, Math.min(12, sceneDuration / 3)], [0, 1], clamp);
  const exit = interpolate(localFrame, [Math.max(0, sceneDuration - 12), sceneDuration], [1, 0], clamp);
  const caption = project.captions.find(
    (item) => seconds >= item.startSec && seconds < item.endSec,
  );
  const progress = frame / Math.max(1, durationInFrames - 1);

  return (
    <AbsoluteFill style={{fontFamily: "Arial, Helvetica, sans-serif", color: "white"}}>
      <Background accent={scene.accent ?? project.brand.primaryColor} progress={progress} />
      {project.voiceoverFile ? <Audio src={staticFile(project.voiceoverFile)} volume={1} /> : null}

      <div style={{position: "absolute", inset: 0, opacity: enter * exit}}>
        <VisualStage scene={scene} localFrame={localFrame} />
        <div
          style={{
            position: "absolute",
            left: 64,
            right: 64,
            top: 150,
            opacity: enter,
          }}
        >
          <div
            style={{
              fontSize: 24,
              fontWeight: 900,
              letterSpacing: ".14em",
              color: scene.accent ?? project.brand.primaryColor,
            }}
          >
            REAL FACT · ANIMATED EXPLANATION
          </div>
          <div
            style={{
              maxWidth: 900,
              marginTop: 18,
              fontSize: 66,
              fontWeight: 950,
              lineHeight: 1.02,
              letterSpacing: "-.045em",
            }}
          >
            {scene.headline}
          </div>
        </div>
      </div>

      <Caption caption={caption} />

      <div
        style={{
          position: "absolute",
          left: 54,
          right: 54,
          bottom: 80,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 24,
          fontSize: 22,
          fontWeight: 800,
          color: "rgba(255,255,255,.72)",
        }}
      >
        <span>{project.brand.watermark}</span>
        <span>{project.disclosure}</span>
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 18,
          background: "rgba(255,255,255,.15)",
        }}
      >
        <div
          style={{
            width: `${progress * 100}%`,
            height: "100%",
            background: project.brand.primaryColor,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
