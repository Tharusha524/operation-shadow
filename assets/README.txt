ASSETS FOLDER - where real art and sound files go
=================================================

Right now the game builds ALL of its 3D models and textures in Python code
(procedural placeholders). Nothing in here is required to play.
Only use files you made yourself (e.g. in Blender) or that have a licence allowing it
(for example CC0 from Poly Haven, ambientCG, Kenney, Quaternius).
Never use files extracted from other games.

textures/   Replace a generated texture by dropping in an image with the material name:
              concrete  block  asphalt  dirt  metal  corrugated  wood  fabric
              bark  foliage  rock  hesco  chainlink(must have transparency)
            e.g.  textures/concrete.png  or  textures/dirt.jpg
            Use SEAMLESS (tileable) images. They are used automatically on the next start.

models/     Replace a procedural prop by a real model named after the prop type:
              barracks  hangar  watchtower  jeep  truck  container  tree_pine  rock ...
              (full list: PROP_BUILDERS at the bottom of environments/props.py)
            e.g.  models/jeep.bam  or  models/jeep.egg
            Model rules: 1 unit = 1 metre, origin at the bottom centre, front facing +Y, Z up.
            Blender can export .egg/.bam with the "blend2bam" tool (pip install panda3d-blend2bam).
            Collisions keep using the procedural shapes, so keep the same size.

sounds/     Replace any generated sound by a file with the same name (.wav or .ogg), e.g.
              shot_rifle  shot_pistol  shot_sniper  shot_shotgun  shot_enemy  reload_out  reload_in
              footstep_0..3  explosion  impact_hard  impact_flesh  wind_loop  alarm_loop  radio_beep
            (full list: _recipes() in systems/sound_synth.py). Use MONO files for 3D-positioned sounds.
music/      music_menu.ogg replaces the generated menu music.
fonts/      ui.ttf replaces the menu font (otherwise Windows' Bahnschrift font is used).

Soldiers    The soldiers are procedural placeholders (enemies/soldier_model.py). A rigged character
            made in Blender (exported with blend2bam) can replace them later - the AI and hit boxes
            do not depend on the model.
