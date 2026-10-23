{
  "character": "edu_woman_v1",
  "style_match": "edu_man_v1 - same colors and joint style",
  "colors": {
    "skin": "#F9D5B0",
    "shirt": "#4FA8B3",
    "pants": "#D8CBB0",
    "shoes": "#8B7E74",
    "hair": "#2E2B29"
  },
  "joints_front_view": {
    "head_top": [0.50, 0.145],
    "neck": [0.50, 0.258],
    "l_shoulder": [0.365, 0.328],
    "r_shoulder": [0.635, 0.328],
    "l_elbow": [0.235, 0.432],
    "r_elbow": [0.765, 0.432],
    "l_wrist": [0.118, 0.512],
    "r_wrist": [0.882, 0.512],
    "l_hip": [0.415, 0.532],
    "r_hip": [0.585, 0.532],
    "l_knee": [0.372, 0.692],
    "r_knee": [0.628, 0.692],
    "l_ankle": [0.348, 0.866],
    "r_ankle": [0.652, 0.866]
  },
  "joints_side_view": {
    "neck": [0.722, 0.262],
    "shoulder": [0.720, 0.335],
    "elbow": [0.720, 0.448],
    "wrist": [0.730, 0.565],
    "hip": [0.715, 0.535],
    "knee": [0.716, 0.702],
    "ankle": [0.722, 0.870]
  },
  "notes_for_claude": {
    "difference_from_man": "only hair shape and slight torso taper, all joint positions almost identical so same animation code works for both",
    "hair": "treat hair as child of head, same pivot as head",
    "rig_groups": "g-head, g-neck, g-torso, g-l-upperArm, g-l-lowerArm, g-r-upperArm, g-r-lowerArm, g-l-thigh, g-l-shin, g-r-thigh, g-r-shin - same as man",
    "reuse": "Use same motion function for man and woman: rotate(l_thigh, hip) etc. No extra code needed"
  }
}