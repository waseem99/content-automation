import React from "react";
import {Composition} from "remotion";
import sampleProject from "../samples/rawr-nation-army-ants.json";
import {RawrNationShort} from "./RawrNationShort";
import type {VideoInputProps, VideoProject} from "./types";

const sample = sampleProject as VideoProject;

export const VideoRoot: React.FC = () => {
  return (
    <Composition<VideoInputProps>
      id="RawrNationShort"
      component={RawrNationShort}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={Math.ceil(sample.render.durationSeconds * sample.render.fps)}
      defaultProps={{project: sample}}
      calculateMetadata={({props}) => ({
        width: props.project.render.width,
        height: props.project.render.height,
        fps: props.project.render.fps,
        durationInFrames: Math.ceil(
          props.project.render.durationSeconds * props.project.render.fps,
        ),
      })}
    />
  );
};
