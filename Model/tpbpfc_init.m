% -------------------------------------------------------------------------------
%            __________  ____  ____  ____________   ____      _ __
%           /_  __/ __ \/ __ )/ __ \/ ____/ ____/  /  _/___  (_) /_
%            / / / /_/ / __  / /_/ / /_  / /       / // __ \/ / __/
%           / / / ____/ /_/ / ____/ __/ / /___   _/ // / / / / /_
%          /_/ /_/   /_____/_/   /_/    \____/  /___/_/ /_/_/\__/
%
%
% Name:        tpbpfc_init.m
% Purpose:     1 kW Totem-Pole Bridgeless PFC (single leg, non-interleaved)
%              PLECS model initialization script.
%              Paste into (or call from) the PLECS model initialization commands:
%                Simulation > Simulation Parameters > Initialization
%              Octave/MATLAB compatible. All values are SI units.
%
% Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
%
% Created:     10/16/2026
% Licence:     Refer to the LICENSE file
% -------------------------------------------------------------------------------
% -------------------------------------------------------------------------------

%% ---------------------------- Specifications ----------------------------
Spec.Po        = 1000;          % Rated output power [W]
Spec.Vo        = 400;           % Output DC voltage [V]
Spec.Vin_min   = 85;            % Minimum input voltage [Vrms]
Spec.Vin_nom   = 230;           % Nominal input voltage [Vrms]
Spec.Vin_max   = 265;           % Maximum input voltage [Vrms]
Spec.f_line    = 50;            % Line frequency [Hz]
Spec.eta       = 0.97;          % Estimated efficiency [-]
Spec.ripple_iL = 0.30;          % Inductor p-p ripple / peak line current at Vin_min [-]
Spec.dVo_pp    = 0.05*Spec.Vo;  % Output 2*f_line p-p ripple [V]
Spec.t_hold    = 10e-3;         % Hold-up time [s]
Spec.Vo_hold   = 300;           % Minimum Vo at end of hold-up [V]

%% ------------------------------ AC source -------------------------------
Source.Vin = Spec.Vin_nom;      % [Vrms]  (used by the source subsystem)
Source.f   = Spec.f_line;       % [Hz]
Source.R   = 0.1;               % Line series resistance (each conductor) [Ohm]

%% ------------------------------ EMI filter ------------------------------
Filter.Rs     = 10e-3;          % Series resistance [Ohm]
Filter.Cx     = 1e-6;           % X capacitor [F]
Filter.Cy     = 2.2e-9;         % Y capacitors (each) [F]
Filter.Rbleed = 470e3;          % Bleeder resistors (each) [Ohm]
Filter.Lcm    = 5e-3;           % Common-mode choke inductance [H]
Filter.Llk    = 20e-6;          % CMC leakage (differential-mode) [H]

%% --------------------------- Power stage --------------------------------
PS.fsw   = 80e3;                % Switching frequency (fast leg) [Hz]
PS.Tsw   = 1/PS.fsw;
PS.t_dead = 100e-9;             % Fast-leg dead time [s]

% Peak line current at low line, full load
PS.Iin_pk = sqrt(2)*Spec.Po/(Spec.eta*Spec.Vin_min);

% Boost inductor: worst-case ripple occurs where Vin_pk = Vo/2
PS.dIL = Spec.ripple_iL*PS.Iin_pk;
PS.L   = Spec.Vo/(4*PS.fsw*PS.dIL);
PS.RL  = 50e-3;                 % Inductor DCR [Ohm]

% Output capacitor: max of ripple and hold-up requirements
PS.Co_ripple = Spec.Po/(2*pi*Spec.f_line*Spec.Vo*Spec.dVo_pp);
PS.Co_hold   = 2*Spec.Po*Spec.t_hold/(Spec.Vo^2 - Spec.Vo_hold^2);
PS.Co        = max(PS.Co_ripple, PS.Co_hold);
PS.Co_esr    = 50e-3;           % [Ohm]

% Switches (fast leg: GaN/SiC, slow leg: Si line-frequency)
PS.Fast.Ron = 50e-3;            % HS1/LS1 on-resistance [Ohm]
PS.Fast.Coss = 100e-12;         % [F]
PS.Slow.Ron = 30e-3;            % HS2/LS2 on-resistance [Ohm]

% Load
PS.Rload = Spec.Vo^2/Spec.Po;   % [Ohm]

%% ------------------------------- Control --------------------------------
Ctrl.fs   = PS.fsw;             % Control sample rate (1 update / PWM period) [Hz]
Ctrl.Ts   = 1/Ctrl.fs;
Ctrl.Vref = Spec.Vo;            % [V]

% Inner current loop (plant ~ Vo/(s*L)): first-cut PI at fc_i
Ctrl.I.fc = PS.fsw/10;
Ctrl.I.Kp = 2*pi*Ctrl.I.fc*PS.L/Spec.Vo;
Ctrl.I.Ki = Ctrl.I.Kp*2*pi*Ctrl.I.fc/5;

% Outer voltage loop: bandwidth well below 2*f_line
Ctrl.V.fc = 10;
Ctrl.V.Kp = 2*pi*Ctrl.V.fc*PS.Co;
Ctrl.V.Ki = Ctrl.V.Kp*2*pi*Ctrl.V.fc/5;

% Measurement / zero-crossing handling
Ctrl.Vzc_th = 20;               % |Vin| below which the slow leg is held off [V]
Ctrl.soft_start_t = 50e-3;      % Vref ramp time [s]

%% ---------------------------- Simulation --------------------------------
Sim.t_stop = 0.2;               % [s]
Sim.Vo0    = sqrt(2)*Source.Vin;% Pre-charged Cout (inrush bypass assumed) [V]
