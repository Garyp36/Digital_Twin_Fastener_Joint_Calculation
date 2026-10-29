# Fastener Joint Digital Twin

A Streamlit demo for fastener joint design, verification, and remaining useful life (RUL) analysis.

## Modes

- **Design Mode**: Flanged hex screw and TS 17426 square weld nut with collar, sizes M6-M12.
- **Verification Mode**: Geometry and fastener specification checks. The PLM button loads local demo records; it does not connect to a live PLM system.
- **RUL Model 1: FOS Model**: Linear Toff/preload retention through the FoS-scaled cycle horizon.
- **RUL Model 2: CAE Model**: Uses a cycle-indexed CAE retention CSV.
- **RUL Model 3: Test Model**: Uses a cycle-indexed physical test retention CSV.

## Run locally

Use Python 3.9 or newer. The requirements select Matplotlib 3.9.0 for Python 3.9 and Matplotlib 3.11.2 for Python 3.10 or newer (including Python 3.14). From this folder, install the pinned packages and start Streamlit:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m streamlit run app.py
```

The terminal prints the local URL to open in a browser. Close Streamlit with `Ctrl+C` in that terminal.

## Publish through GitHub and Streamlit Community Cloud

1. Upload the files in this folder to the root of a GitHub repository and push the commit.
2. In Streamlit Community Cloud, create an app and select that repository and branch.
3. Set the main file path to `app.py`, then deploy.
4. Keep `requirements.txt` in the repository root so the cloud app installs its dependencies.

The app does not need secrets or external services for the demo.

## CSV formats

### Assembly-line torque

Use `rul_mat_torque_template.csv` or the in-app download. Fill one row per vehicle/fastener:

```csv
MAT number,Torque value
MAT-001,1.00
```

Choose the matching torque unit in the app. Torque values must be finite and greater than zero.

### CAE and Test results

Use `rul_cae_trend_template.csv` or `rul_test_results_template.csv`. Both have the same normalized retention format:

```csv
Cycle,Toff retention (%),Preload retention (%)
0,100,100
400,98.5,99
```

The trend must start at cycle 0 with both retention values at 100%, and it must include data through `Mission cycles × FoS`. Extend the template if the selected horizon is greater than 3,200 cycles. The included declining values are examples, not measured CAE or test results.

Each MAT starts with estimated Toff equal to 90% of its assembly Ton. The uploaded normalized Toff trend is scaled to that starting value. The app compares each MAT's Toff with the selected database reference limit and schedules the re-torque check using the configured kilometre lead.

## Demo limitations

- Torque, preload, geometry, and proof-stress values are embedded prototype tables. Confirm them against the approved, revision-controlled engineering database before using results for design release.
- The PLM action uses local sample records only.
- Preload for MAT-specific assembly torque is scaled in proportion to database preload and assembly Ton. This is a demo assumption.
- Bearing area is a geometric net contact-area estimate from flange/hole overlap. It does not calculate contact pressure, load distribution, or edge breakout.
- The app is a workflow demonstration and is not a substitute for an approved engineering analysis or validation process.
