import React from "react";
import {Composition} from "remotion";
import sampleProject from "../samples/rawr-nation-army-ants.json";
import {RawrNationShort} from "./RawrNationShort";
import {ReferenceStoryShort} from "./ReferenceStoryShort";
import type {VideoProject} from "./types";

const sample = sampleProject as VideoProject;
const metadata = ({props}: {props: {project: VideoProject}}) => ({
  width: props.project.render.width,
  height: props.project.render.height,
  fps: props.project.render.fps,
  durationInFrames: Math.ceil(
    props.project.render.durationSeconds * props.project.render.fps,
  ),
});

export const VideoRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="RawrNationShort"
        component={RawrNationShort}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={Math.ceil(sample.render.durationSeconds * sample.render.fps)}
        defaultProps={{project: sample}}
        calculateMetadata={metadata}
      />
      <Composition
        id="ReferenceStoryShort"
        component={ReferenceStoryShort}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={Math.ceil(sample.render.durationSeconds * sample.render.fps)}
        defaultProps={{project: sample}}
        calculateMetadata={metadata}
      />
    </>
  );
};
