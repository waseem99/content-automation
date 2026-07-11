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

const Background: React.FC<{primary: string; secondary: string; progress: number}> = ({
  primary,
  secondary,
  progress,
}) => {
  const drift = interpolate(progress, [0, 1], [-120, 160]);
  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        background:
          "radial-gradient(circle at 20% 10%, rgba(255,255,255,.14), transparent 27%), linear-gradient(165deg, #070A10 0%, #111A27 52%, #080C13 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: -360 + drift,
          top: 260,
          width: 820,
          height: 820,
          borderRadius: "50%",
          background: primary,
          opacity: 0.16,
          filter: "blur(24px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          right: -300 - drift,
          bottom: 140,
          width: 690,
          height: 690,
          borderRadius: "50%",
          border: `5px solid ${secondary}`,
          opacity: 0.12,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.07,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.18) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.18) 1px, transparent 1px)",
          backgroundSize: "68px 68px",
        }}
      />
    </AbsoluteFill>
  );
};

const Eye: React.FC<{x: number; y: number; scale?: number; accent: string; blink?: number}> = ({
  x,
  y,
  scale = 1,
  accent,
  blink = 1,
}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: 460,
      height: 250,
      transform: `scale(${scale}) scaleY(${blink})`,
      borderRadius: "50% / 58%",
      border: "18px solid rgba(255,255,255,.94)",
      background: "rgba(255,255,255,.08)",
      boxShadow: `0 0 70px ${accent}44`,
    }}
  >
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        width: 150,
        height: 150,
        transform: "translate(-50%,-50%)",
        borderRadius: "50%",
        background: accent,
        boxShadow: `inset 0 0 0 38px #0A101B, 0 0 45px ${accent}88`,
      }}
    />
  </div>
);

const VisionHook: React.FC<{frame: number; accent: string}> = ({frame, accent}) => {
  const pop = spring({frame, fps: 30, config: {damping: 14, stiffness: 120}});
  const blink = frame % 110 > 96 ? 0.12 : 1;
  return (
    <div style={{position: "absolute", inset: 0}}>
      <Eye x={310} y={670} scale={0.98 + pop * 0.12} accent={accent} blink={blink} />
      <div
        style={{
          position: "absolute",
          left: 470,
          top: 742,
          width: 138,
          height: 138,
          borderRadius: "50%",
          border: `8px dashed ${accent}`,
          transform: `rotate(${frame * 1.4}deg) scale(${0.8 + pop * 0.35})`,
        }}
      />
    </div>
  );
};

const BlindSpotGrid: React.FC<{frame: number; accent: string}> = ({frame, accent}) => {
  const reveal = interpolate(frame, [20, 95], [0, 1], clamp);
  return (
    <div
      style={{
        position: "absolute",
        left: 135,
        right: 135,
        top: 620,
        height: 650,
        borderRadius: 48,
        overflow: "hidden",
        backgroundImage:
          "linear-gradient(rgba(255,255,255,.22) 3px, transparent 3px), linear-gradient(90deg, rgba(255,255,255,.22) 3px, transparent 3px)",
        backgroundSize: "82px 82px",
        border: "3px solid rgba(255,255,255,.18)",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 310,
          top: 230,
          width: 220,
          height: 220,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accent} ${reveal * 45}%, #05070B ${
            48 + reveal * 30
          }%)`,
          boxShadow: `0 0 80px ${accent}66`,
        }}
      />
    </div>
  );
};

const EyeToBrain: React.FC<{frame: number; accent: string}> = ({frame, accent}) => {
  const flow = (frame * 7) % 620;
  return (
    <div style={{position: "absolute", inset: 0}}>
      <Eye x={90} y={760} scale={0.65} accent={accent} />
      <div
        style={{
          position: "absolute",
          left: 430,
          top: 870,
          width: 480,
          height: 28,
          borderRadius: 999,
          background: "rgba(255,255,255,.12)",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: Math.min(flow, 430),
            top: -12,
            width: 54,
            height: 54,
            borderRadius: "50%",
            background: accent,
            boxShadow: `0 0 34px ${accent}`,
          }}
        />
      </div>
      <div
        style={{
          position: "absolute",
          right: 92,
          top: 690,
          width: 330,
          height: 370,
          borderRadius: "48% 52% 45% 55% / 54% 44% 56% 46%",
          background: `radial-gradient(circle at 35% 30%, ${accent}, #7029A8 55%, #24113B)`,
          border: "10px solid rgba(255,255,255,.72)",
          boxShadow: `0 0 90px ${accent}44`,
        }}
      />
    </div>
  );
};

const FillInVisual: React.FC<{frame: number; accent: string}> = ({frame, accent}) => {
  const fill = spring({frame, fps: 30, config: {damping: 18, stiffness: 80}});
  return (
    <div
      style={{
        position: "absolute",
        left: 130,
        right: 130,
        top: 610,
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 24,
      }}
    >
      {Array.from({length: 9}).map((_, index) => {
        const center = index === 4;
        return (
          <div
            key={index}
            style={{
              height: 190,
              borderRadius: 34,
              background: center
                ? `linear-gradient(135deg, ${accent}, #FFFFFF)`
                : "linear-gradient(135deg, rgba(255,255,255,.18), rgba(255,255,255,.04))",
              border: "2px solid rgba(255,255,255,.17)",
              opacity: center ? fill : 1,
              transform: center ? `scale(${0.55 + fill * 0.45})` : "scale(1)",
            }}
          />
        );
      })}
    </div>
  );
};

const Elephant: React.FC<{x: number; y: number; scale?: number; accent: string; opacity?: number}> = ({
  x,
  y,
  scale = 1,
  accent,
  opacity = 1,
}) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: 360,
      height: 270,
      transform: `scale(${scale})`,
      transformOrigin: "bottom center",
      opacity,
    }}
  >
    <div
      style={{
        position: "absolute",
        left: 70,
        top: 45,
        width: 230,
        height: 155,
        borderRadius: "48% 46% 42% 44%",
        background: accent,
        boxShadow: "0 28px 60px rgba(0,0,0,.35)",
      }}
    />
    <div
      style={{
        position: "absolute",
        left: 10,
        top: 65,
        width: 130,
        height: 130,
        borderRadius: "50%",
        background: accent,
      }}
    />
    <div
      style={{
        position: "absolute",
        left: -8,
        top: 95,
        width: 48,
        height: 145,
        borderRadius: "25px 25px 40px 40px",
        background: accent,
        transform: "rotate(7deg)",
      }}
    />
    {[95, 150, 235, 285].map((left) => (
      <div
        key={left}
        style={{
          position: "absolute",
          left,
          top: 165,
          width: 38,
          height: 92,
          borderRadius: "0 0 18px 18px",
          background: accent,
        }}
      />
    ))}
    <div
      style={{
        position: "absolute",
        left: 48,
        top: 54,
        width: 90,
        height: 110,
        borderRadius: "50%",
        border: "8px solid rgba(255,255,255,.38)",
      }}
    />
  </div>
);

const ElephantHook: React.FC<{frame: number; accent: string}> = ({frame, accent}) => {
  const pop = spring({frame, fps: 30, config: {damping: 15, stiffness: 110}});
  return (
    <div style={{position: "absolute", inset: 0}}>
      <Elephant x={350} y={720} scale={1.05 + pop * 0.2} accent={accent} />
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          style={{
            position: "absolute",
            left: 540 - (180 + index * 90),
            top: 980 - (180 + index * 90) / 2,
            width: (180 + index * 90) * 2,
            height: 180 + index * 90,
            borderRadius: "50%",
            border: `7px solid ${accent}`,
            opacity: 0.35 - index * 0.07,
            transform: `scale(${0.82 + ((frame + index * 10) % 45) / 180})`,
          }}
        />
      ))}
    </div>
  );
};

const HerdVisual: React.FC<{frame: number; accent: string}> = ({frame, accent}) => (
  <div style={{position: "absolute", inset: 0}}>
    {Array.from({length: 5}).map((_, index) => {
      const x = 60 + ((index * 230 + frame * (0.5 + index * 0.08)) % 1060);
      const y = 710 + (index % 2) * 220;
      return (
        <Elephant
          key={index}
          x={x}
          y={y}
          scale={0.42 + (index % 3) * 0.08}
          accent={index === 2 ? accent : "#8997A8"}
          opacity={0.75 + (index % 2) * 0.2}
        />
      );
    })}
  </div>
);

const GroundSignal: React.FC<{frame: number; accent: string}> = ({frame, accent}) => (
  <div style={{position: "absolute", inset: 0}}>
    <Elephant x={120} y={760} scale={0.7} accent={accent} />
    <Elephant x={720} y={760} scale={0.7} accent="#C1CBD7" />
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: 1110,
        height: 18,
        background: "rgba(255,255,255,.22)",
      }}
    />
    {Array.from({length: 7}).map((_, index) => {
      const x = ((frame * 8 + index * 190) % 1280) - 100;
      return (
        <div
          key={index}
          style={{
            position: "absolute",
            left: x,
            top: 1070,
            width: 90,
            height: 90,
            borderRadius: "50%",
            border: `7px solid ${accent}`,
            opacity: 0.25 + (index % 3) * 0.16,
          }}
        />
      );
    })}
  </div>
);

const RevealCards: React.FC<{frame: number; accent: string; labels: string[]}> = ({
  frame,
  accent,
  labels,
}) => {
  const entry = spring({frame, fps: 30, config: {damping: 17, stiffness: 110}});
  return (
    <div
      style={{
        position: "absolute",
        left: 120,
        right: 120,
        top: 640,
        display: "grid",
        gap: 28,
        opacity: entry,
        transform: `translateY(${interpolate(entry, [0, 1], [100, 0])}px)`,
      }}
    >
      {labels.map((label, index) => (
        <div
          key={label}
          style={{
            padding: "34px 42px",
            minHeight: 150,
            borderRadius: 38,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 42,
            fontWeight: 900,
            background: index === 1 ? accent : "rgba(255,255,255,.08)",
            color: index === 1 ? "#071018" : "#FFFFFF",
            border: "2px solid rgba(255,255,255,.15)",
          }}
        >
          <span>{String(index + 1).padStart(2, "0")}</span>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
};

const CtaVisual: React.FC<{
  frame: number;
  accent: string;
  brand: string;
  tagline: string;
  cta: string;
}> = ({frame, accent, brand, tagline, cta}) => {
  const pop = spring({frame, fps: 30, config: {damping: 14, stiffness: 120}});
  return (
    <div
      style={{
        position: "absolute",
        left: 100,
        right: 100,
        top: 600,
        padding: "78px 58px",
        borderRadius: 62,
        background: "rgba(255,255,255,.96)",
        color: "#0B1018",
        textAlign: "center",
        transform: `scale(${interpolate(pop, [0, 1], [0.75, 1])})`,
        opacity: pop,
      }}
    >
      <div style={{fontSize: 38, fontWeight: 950, color: accent, letterSpacing: ".11em"}}>
        {brand.toUpperCase()}
      </div>
      <div style={{fontSize: 70, fontWeight: 950, lineHeight: 1.03, marginTop: 30}}>{cta}</div>
      <div style={{fontSize: 28, color: "#4B5563", marginTop: 28}}>{tagline}</div>
    </div>
  );
};

const VisualStage: React.FC<{
  scene: StoryScene;
  localFrame: number;
  theme: string;
  brand: VideoInputProps["project"]["brand"];
}> = ({scene, localFrame, theme, brand}) => {
  const accent = scene.accent ?? brand.primaryColor;
  if (scene.visual === "cta") {
    return (
      <CtaVisual
        frame={localFrame}
        accent={accent}
        brand={brand.name}
        tagline={brand.tagline}
        cta={scene.body}
      />
    );
  }
  if (theme === "elephants") {
    if (scene.visual === "hook") return <ElephantHook frame={localFrame} accent={accent} />;
    if (scene.visual === "swarm") return <HerdVisual frame={localFrame} accent={accent} />;
    if (scene.visual === "bridge" || scene.visual === "traffic") {
      return <GroundSignal frame={localFrame} accent={accent} />;
    }
    return <RevealCards frame={localFrame} accent={accent} labels={["RUMBLE", "GROUND", "MESSAGE"]} />;
  }
  if (scene.visual === "hook") return <VisionHook frame={localFrame} accent={accent} />;
  if (scene.visual === "swarm") return <BlindSpotGrid frame={localFrame} accent={accent} />;
  if (scene.visual === "bridge") return <EyeToBrain frame={localFrame} accent={accent} />;
  if (scene.visual === "traffic") return <FillInVisual frame={localFrame} accent={accent} />;
  return <RevealCards frame={localFrame} accent={accent} labels={["RETINA", "MISSING", "FILLED"]} />;
};

const Caption: React.FC<{caption?: CaptionChunk}> = ({caption}) => {
  if (!caption) return null;
  const words = caption.text.split(/\s+/);
  const target = caption.highlight?.replace(/[^a-z0-9]/gi, "").toLowerCase();
  const color = highlightColors[caption.emphasis ?? "neutral"];
  return (
    <div
      style={{
        position: "absolute",
        left: 64,
        right: 64,
        bottom: 238,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "4px 18px",
        textAlign: "center",
        fontSize: 67,
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
        return (
          <span key={`${word}-${index}`} style={{color: target && normalized === target ? color : "#FFFFFF"}}>
            {word}
          </span>
        );
      })}
    </div>
  );
};

export const ReferenceStoryShort: React.FC<VideoInputProps> = ({project}) => {
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
  const theme = project.visualTheme ?? "vision";

  return (
    <AbsoluteFill style={{fontFamily: "Arial, Helvetica, sans-serif", color: "white"}}>
      <Background
        primary={scene.accent ?? project.brand.primaryColor}
        secondary={project.brand.secondaryColor}
        progress={progress}
      />
      {project.voiceoverFile ? <Audio src={staticFile(project.voiceoverFile)} volume={1} /> : null}
      <div style={{position: "absolute", inset: 0, opacity: enter * exit}}>
        <VisualStage scene={scene} localFrame={localFrame} theme={theme} brand={project.brand} />
        <div style={{position: "absolute", left: 64, right: 64, top: 145, opacity: enter}}>
          <div
            style={{
              fontSize: 24,
              fontWeight: 900,
              letterSpacing: ".14em",
              color: scene.accent ?? project.brand.primaryColor,
            }}
          >
            {project.brand.tagline.toUpperCase()}
          </div>
          <div
            style={{
              maxWidth: 900,
              marginTop: 18,
              fontSize: 65,
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
          bottom: 78,
          display: "flex",
          justifyContent: "space-between",
          gap: 24,
          fontSize: 21,
          fontWeight: 800,
          color: "rgba(255,255,255,.72)",
        }}
      >
        <span>{project.brand.watermark}</span>
        <span>{project.disclosure}</span>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 18, background: "rgba(255,255,255,.15)"}}>
        <div style={{width: `${progress * 100}%`, height: "100%", background: project.brand.primaryColor}} />
      </div>
    </AbsoluteFill>
  );
};
