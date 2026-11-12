#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?                 __  __
#?           _____/ /_/ /_  ____  _  __
#?          / ___/ __/ __ \/ __ \| |/_/
#?         / /  / /_/ /_/ / /_/ />  <
#?        /_/   \__/_.___/\____/_/|_|
#?
#?
#? Name:        rtbox.py
#? Purpose:     hardware-in-the-loop copy of a PLECS model (<model>_rtbox.plecs) for a PLECS RT Box:
#?              - standalone (library links broken, ModelVars written as values: breaklink.py, standalone.py);
#?              - everything but the controller moved into the subsystem 'Plant', with code generation enabled
#?                for the RT Box; the gates come from a PWM Capture block, the signals the controller reads go
#?                to Analog Out blocks;
#?              - the controller stays next to the plant and closes the loop in the offline simulation; on the
#?                bench it runs on its own board, wired to the RT Box.
#?              Standard library only; needs breaklink.py and standalone.py next to it.
#?                  path = RTBoxModel.write('model.plecs', ModelVars, ['lib_dir'], controller='MCU')
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     11/12/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import copy
import re
from   pathlib              import  Path

try:
    from   .breaklink       import  LinkBreaker, PlecsBlock                  # inside a package (from lib.rtbox import ...)
    from   .standalone      import  Standalone
except ImportError:
    from   breaklink        import  LinkBreaker, PlecsBlock                  # run as a script, the two files next to it
    from   standalone       import  Standalone

NL                                  = chr(10)
#?----------------------------------------------------------------------------------------------------------------------------------------
class RTBoxModel:
    """Hardware-in-the-loop copy of a PLECS model for a PLECS RT Box.

        path = RTBoxModel.write(model_path, modelvars, lib_dir=None, out=None, controller='MCU', offline=(), ...)

    model_path  .plecs model; the controller is one subsystem on its top level, connected to the rest through
                From blocks (the signals it reads) and one Goto block (the gate bus it drives)
    modelvars   {name: value} of the operating point, written into the model (see standalone.py)
    lib_dir     folder(s) of the user libraries
    out         output file (default <model>_rtbox.plecs next to the model)
    controller  name of the controller subsystem (stays outside the plant)
    offline     top-level blocks that stay outside the plant and are not part of the generated code (scopes, data export)
    target      code generation target of the plant
    step        discretization step of the plant [s] (expression)
    gates       digital input channels of the gate signals (expression: vector); n_gates = how many
    gate_width  width of the gate bus the plant expects (the signals after the first n_gates are 0); None = n_gates
    analog      analog output channels of the signals the controller reads, in the order of its inputs (expression: vector)
    analog_max  upper limit of the analog outputs [V] (expression), lower limit 0

    The code generation path of the plant is '<model>_rtbox/Plant' (RTBoxModel.PLANT).
    """

    SUFFIX                          = '_rtbox'
    PLANT                           = 'Plant'
    TAG_SUFFIX                      = '_rt'                                     # tags copied outside the plant for the offline blocks
    VIEW                            = ('Location', 'ZoomFactor', 'SliderPosition', 'ShowBrowser', 'BrowserWidth')
    P_PLANT, P_CTRL                 = (400, 150), (400, 360)                    # places on the new top level
    FRAME                           = 60                                        # half size of the plant block

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? One-line entry point
    #?------------------------------------------------------------------------------------------------------------------------------------
    @classmethod
    def write(cls, model_path, modelvars=None, lib_dir=None, out=None, controller='MCU', offline=(), target='PLECS RT Box 1',
              step='RTBox.Ts', gates='RTBox.DI_gate', n_gates=4, gate_width=None, analog='RTBox.AO_sns', analog_max='RTBox.AO_max',
              builtins=True):
        lb                          = LinkBreaker(model_path, lib_dir, builtins)
        out                         = Path(out) if out else lb.model.with_name(lb.model.stem + cls.SUFFIX + lb.model.suffix)
        Standalone.set_vars(lb, modelvars, tag='rtbox')
        self                        = cls(lb, controller, offline)
        self.build(target, step, gates, n_gates, gate_width or n_gates, analog, analog_max)
        path                        = lb.save(out, tag='rtbox')
        print(f"rtbox: plant '{out.stem}/{cls.PLANT}' ({target}, step {step}): {n_gates} gates on digital inputs {gates}, "
              f"{len(self.inputs)} signals on analog outputs {analog} ({', '.join(self.signals)})")
        return path

    def __init__(self, lb, controller, offline):
        self.lb                     = lb
        self.sch                    = lb.plecs.kids('Schematic')[0]
        self.outside                = (controller,) + tuple(offline)
        comps                       = {c.value('Name'): c for c in self.sch.kids('Component')}
        missing                     = [n for n in self.outside if n not in comps]
        if missing:
            raise ValueError(f"not on the top level of the model: {missing}")
        self.ctrl                   = comps[controller]
        self.kept                   = [comps[n] for n in offline]
        self.comps                  = comps
        self.inputs, self.signals   = [], []

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Small helpers
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def blocks(text):
        return PlecsBlock.parse(text).kids()

    @staticmethod
    def param(variable, value):
        return f'  Parameter {{\n    Variable      "{variable}"\n    Value         "{value}"\n    Show          off\n  }}\n'

    @classmethod
    def block(cls, kind, name, pos, params, extra='', show='off'):
        """Text of a basic block facing right."""
        return (f'Component {{\n  Type          {kind}\n{extra}  Name          "{name}"\n  Show          {show}\n  Position      [{pos[0]}, {pos[1]}]\n'
                f'  Direction     right\n  Flipped       off\n  LabelPosition south\n' + ''.join(cls.param(k, v) for k, v in params) + '}')

    @classmethod
    def gain(cls, name, pos, K):
        return cls.block('Gain', name, pos, [('K', K), ('Multiplication', '2'), ('OutputDataType', '11'), ('DataTypeOverflowMode', '1'),
                                             ('GainDataType', '11')])

    @classmethod
    def target_block(cls, lib_block, name, pos, params, terminal):
        """Text of an RT Box library block (kept as a library link)."""
        kind, tpos, tdir            = terminal
        return (f'Component {{\n  Type          Reference\n  SrcComponent  "PLECSRTBoxLib/{lib_block}"\n  Name          "{name}"\n  Show          on\n'
                f'  Position      [{pos[0]}, {pos[1]}]\n  Direction     up\n  Flipped       off\n  LabelPosition south\n  Frame         [-25, -20; 25, 20]\n'
                + ''.join(cls.param(k, v) for k, v in params) +
                f'  Terminal {{\n    Type          {kind}\n    Position      {tpos}\n    Direction     {tdir}\n  }}\n}}')

    @staticmethod
    def signal(src, st, dst, dt, points=None):
        pts                         = f"  Points        [{'; '.join(f'{x}, {y}' for x, y in points)}]\n" if points else ''
        return (f'Connection {{\n  Type          Signal\n  SrcComponent  "{src}"\n  SrcTerminal   {st}\n{pts}  DstComponent  "{dst}"\n'
                f'  DstTerminal   {dt}\n}}')

    @staticmethod
    def ends(conn):
        """[(component, terminal)] at the ends of a connection, source first."""
        out                         = [(conn.value(s + 'Component'), int(conn.raw(s + 'Terminal'))) for s in ('Src', 'Dst') if conn.value(s + 'Component')]
        for b in conn.kids('Branch'):
            out                    += RTBoxModel.ends(b)
        return out

    @staticmethod
    def place(comp, pos):
        comp.set('Position', [f'Position      [{pos[0]}, {pos[1]}]'])
        comp.set('Direction', ['Direction     right'])
        comp.set('Flipped', ['Flipped       off'])

    @staticmethod
    def get(comp, variable):
        return next((p.value('Value') for p in comp.kids('Parameter') if p.value('Variable') == variable), None)

    @staticmethod
    def put(comp, variable, value):
        for p in comp.kids('Parameter'):
            if p.value('Variable') == variable:
                p.set('Value', [f'Value         "{value}"'])

    @classmethod
    def walk(cls, block, kind=None):
        """Every component below block (any depth), of one Type if given."""
        for c in block.kids():
            if c.tag == 'Component' and (kind is None or c.value('Type') == kind):
                yield c
            yield from cls.walk(c, kind)

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Plant / controller split
    #?------------------------------------------------------------------------------------------------------------------------------------
    def build(self, target, step, gates, n_gates, gate_width, analog, analog_max):
        sch, name                   = self.sch, self.ctrl.value('Name')
        view                        = [it for it in sch.items if it[0] == 'prop' and it[1] in self.VIEW]
        ctrl_in, ctrl_out, rest     = {}, {}, []
        for it in sch.items:                                                    # connections of the controller: From -> controller -> Goto
            if it[0] == 'block' and it[1].tag == 'Connection' and name in [c for c, _ in self.ends(it[1])]:
                e                   = self.ends(it[1])
                if len(e) != 2:
                    raise ValueError(f"'{name}': connect each controller port to one From / Goto block (branched connection found: {e})")
                (src, st), (dst, dt) = e
                other               = self.comps[dst if src == name else src]
                if src == name and other.value('Type') == 'Goto':
                    ctrl_out[st]    = other
                elif dst == name and other.value('Type') == 'From':
                    ctrl_in[dt]     = other
                else:
                    raise ValueError(f"'{name}': connect the controller through From / Goto blocks (found '{other.value('Name')}', "
                                     f"{other.value('Type')})")
                continue
            if it[0] == 'block' and it[1].tag == 'Component' and it[1].value('Name') in self.outside:
                continue
            if not (it[0] == 'prop' and it[1] in self.VIEW):
                rest.append(it)
        if len(ctrl_out) != 1:
            raise ValueError(f"'{name}': one output (the gate bus) expected, found {len(ctrl_out)}")
        for c in self.kept:
            if c.value('Name') in [n for it in rest if it[0] == 'block' and it[1].tag == 'Connection' for n, _ in self.ends(it[1])]:
                raise ValueError(f"offline block '{c.value('Name')}' is wired to the plant: connect it through probes or tags")
        self.inputs                 = [ctrl_in[k] for k in sorted(ctrl_in)]
        self.signals                = [self.get(f, 'Tag') or f.value('Name') for f in self.inputs]
        (out_term, goto),           = ctrl_out.items()

        #? I/O blocks, below everything else in the plant
        ys                          = [int(v) for c in sch.kids('Component') if c.value('Name') not in self.outside
                                       for v in re.findall(r'-?\d+', c.raw('Position') or '')[1:2]]
        x0, y0                      = 200, max(ys) + 90
        new, wires                  = [], []
        new.append(self.target_block('PWM Capture1', 'PWM Capture', (x0, y0),
                                     [('channel', gates), ('polarity', '1'), ('inputType', '1'), ('Ts', step), ('offlineBehavior', '1'),
                                      ('TargetPortIndices', '1')], ('Output', '[29, 0]', 'right')))
        self.place(goto, (x0 + 260, y0))
        if gate_width > n_gates:                                                # gate bus wider than the captured signals: the rest is 0
            new.append(self.gain('Gate bus', (x0 + 130, y0), f'[eye({n_gates}); zeros({gate_width - n_gates}, {n_gates})]'))
            wires                  += [self.signal('PWM Capture', 1, 'Gate bus', 1), self.signal('Gate bus', 2, goto.value('Name'), 1)]
        else:
            wires.append(self.signal('PWM Capture', 1, goto.value('Name'), 1))
        for k, (frm, sig) in enumerate(zip(self.inputs, self.signals), 1):
            y                       = y0 + 70 * k
            self.place(frm, (x0, y))
            new.append(self.target_block('Analog Out1', f'AO {sig}', (x0 + 130, y),
                                         [('channel', f'{analog}({k})'), ('scale', '1'), ('offset', '0'), ('minOutput', '0'),
                                          ('maxOutput', analog_max), ('TargetPortIndices', str(k + 1))], ('Input', '[-25, 0]', 'left')))
            wires.append(self.signal(frm.value('Name'), 1, f'AO {sig}', 1))
        last_c                      = max(k for k, it in enumerate(rest) if it[0] == 'block' and it[1].tag == 'Component')
        rest[last_c + 1:last_c + 1] = [['block', b] for b in self.blocks(NL.join(new))]
        last_w                      = max(k for k, it in enumerate(rest) if it[0] == 'block' and it[1].tag == 'Connection')
        rest[last_w + 1:last_w + 1] = [['block', b] for b in self.blocks(NL.join(wires))]

        #? tags and probes that cross the plant boundary
        plant_sch                   = PlecsBlock('Schematic')
        plant_sch.items             = copy.deepcopy(view) + rest
        dup                         = self.cross_tags(plant_sch)
        self.move_probes(plant_sch)

        #? the plant subsystem, with one port per I/O block for the offline simulation
        F, n                        = self.FRAME, len(self.inputs)
        out_y                       = [int(round((k - (n - 1) / 2) * 40)) for k in range(n)]
        terms                       = f'  Terminal {{\n    Type          Input\n    Position      [{-F}, 0]\n    Direction     left\n    Index         "1"\n  }}\n'
        terms                      += ''.join(f'  Terminal {{\n    Type          Output\n    Position      [{F + 4}, {y}]\n    Direction     right\n'
                                              f'    Index         "{k}"\n  }}\n' for k, y in enumerate(out_y, 1))
        px, py                      = self.P_PLANT
        plant                       = self.blocks(
            f'Component {{\n  Type          Subsystem\n  Name          "{self.PLANT}"\n  Show          on\n  Position      [{px}, {py}]\n'
            f'  Direction     up\n  Flipped       off\n  LabelPosition south\n  Frame         [{-F}, {-F}; {F}, {F}]\n  TreatAsAtomicUnit on\n'
            f'  SampleTime    "-1"\n  CodeGenEnable on\n  CodeGenSampleTime "{step}"\n  CodeGenDiscretizationMethod "2"\n'
            f'  CodeGenTarget "{target}"\n  MaskIconFrame on\n  MaskIconOpaque off\n  MaskIconRotates on\n{terms}}}')[0]
        plant.items.append(['block', plant_sch])

        #? new top level: plant, controller, offline blocks; the loop is closed here for the offline simulation
        cx, cy                      = self.P_CTRL
        self.ctrl.set('Position', [f'Position      [{cx}, {cy}]'])
        terminals                   = [(t.value('Type'), [int(v) for v in re.findall(r'-?\d+', t.raw('Position'))], t.value('Direction'))
                                       for t in self.ctrl.kids('Terminal')]
        root_c, root_w              = [plant, self.ctrl], []
        gx, gy                      = px - 150, py                              # gate bus of the controller -> the captured gates
        _, (tx, ty), tdir           = terminals[out_term - 1]
        tx, ty                      = cx + tx, cy + ty
        lane                        = ty - 30 if tdir == 'up' else ty + 30 if tdir == 'down' else ty
        via                         = [(tx, lane), (gx - 70, lane), (gx - 70, gy)] if tdir in ('up', 'down') else [(gx - 70, ty), (gx - 70, gy)]
        if gate_width > n_gates:
            root_c                 += self.blocks(self.gain('Gates', (gx, gy), f'[eye({n_gates}), zeros({n_gates}, {gate_width - n_gates})]'))
            root_w                 += [self.signal(name, out_term, 'Gates', 1, via), self.signal('Gates', 2, self.PLANT, 1)]
        else:
            root_w.append(self.signal(name, out_term, self.PLANT, 1, via + [(gx, gy)]))
        for k, term in enumerate(sorted(ctrl_in), 1):                          # analog outputs -> controller inputs
            _, (tx, ty), tdir       = terminals[term - 1]
            tx, ty                  = cx + tx, cy + ty
            ax, ay                  = px + F + 4, py + out_y[k - 1]
            xr                      = px + F + 60 + 20 * (n - k)
            if tdir in ('up', 'down'):
                yb                  = ty + (25 + 15 * (n - k)) * (1 if tdir == 'down' else -1)
                via                 = [(xr, ay), (xr, yb), (tx, yb)]
            else:
                via                 = [(xr, ay), (xr, ty)]
            root_w.append(self.signal(self.PLANT, k + 1, name, term, via))
        for k, c in enumerate(self.kept):
            c.set('Position', [f'Position      [{150 + 170 * k}, {cy + 190}]'])
            root_c.append(c)
        for k, (src, gto) in enumerate(dup):
            self.place(src, (150 + 170 * len(self.kept) + 60, cy + 190 + 50 * k))
            self.place(gto, (150 + 170 * len(self.kept) + 150, cy + 190 + 50 * k))
            root_c                 += [src, gto]
            root_w.append(self.signal(src.value('Name'), 1, gto.value('Name'), 1))
        sch.items                   = view + [['block', b] for b in root_c] + [['block', b] for b in self.blocks(NL.join(root_w))]

    def cross_tags(self, plant_sch):
        """Global tags set in the plant and read by the blocks outside it: their source block and Goto are copied to
        the top level under a new tag name. Returns [(source copy, Goto copy)]."""
        made                        = {self.get(g, 'Tag') for c in [self.ctrl] + self.kept for g in self.walk(c, 'Goto')}
        used                        = {}
        for c in [self.ctrl] + self.kept:
            for f in self.walk(c, 'From'):
                if self.get(f, 'Tag') not in made:
                    used.setdefault(self.get(f, 'Tag'), []).append(f)
        back                        = {self.get(f, 'Tag') for f in self.walk(plant_sch, 'From')} & \
                                      {self.get(g, 'Tag') for c in [self.ctrl] + self.kept for g in self.walk(c, 'Goto') if self.get(g, 'Visibility') == '1'} - \
                                      {self.get(g, 'Tag') for g in self.walk(plant_sch, 'Goto')}
        if back:
            raise ValueError(f"the plant reads tags set outside it: {sorted(back)}")
        top                         = {c.value('Name'): c for c in plant_sch.kids('Component')}
        wires                       = [self.ends(c) for c in plant_sch.kids('Connection')]
        dup                         = []
        for tag, froms in used.items():
            goto                    = next((c for c in top.values() if c.value('Type') == 'Goto' and self.get(c, 'Tag') == tag), None)
            if goto is None:
                raise ValueError(f"tag '{tag}' is read outside the plant but its Goto is not on the top level of the model")
            src                     = next((e[0][0] for e in wires if (goto.value('Name'), 1) in e[1:]), None)
            if src is None or any(src in [n for n, _ in e[1:]] for e in wires):
                raise ValueError(f"tag '{tag}' is read outside the plant: only a tag driven by a source block (Clock, Constant ...) can be copied")
            s, g                    = copy.deepcopy(top[src]), copy.deepcopy(goto)
            s.set('Name', [f'Name          "{src}{self.TAG_SUFFIX}"']); g.set('Name', [f'Name          "{goto.value("Name")}{self.TAG_SUFFIX}"'])
            self.put(g, 'Tag', tag + self.TAG_SUFFIX)
            for f in froms:
                self.put(f, 'Tag', tag + self.TAG_SUFFIX)
            dup.append((s, g))
        return dup

    def move_probes(self, plant_sch):
        """Probe blocks address components from the top of the model: prefix the paths of what moved into the plant."""
        for holder in [plant_sch, self.ctrl] + self.kept:
            for probe in self.walk(holder, 'PlecsProbe'):
                for p in probe.kids('Probe'):
                    path            = p.value('Path') or ''
                    first           = re.split(r'(?<!\\)/', path)[0].replace('\\\\/', '/').replace('\\/', '/') if path else p.value('Component')
                    if first in self.outside:
                        continue
                    p.set('Path', [f'Path          "{self.PLANT}{"/" + path if path else ""}"'])
#?----------------------------------------------------------------------------------------------------------------------------------------
#? Run this file (VS Code: Run Python File, the play button) to write the RT Box copy with the values saved in the model.
#? With parameters from Python (ModelVars), call RTBoxModel.write from your script (see main.py).
#?----------------------------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    MODEL                           = r'D:\WORKSPACE\0049_SP_BTP_PFC_1KW\model\PFC.plecs'      # model to copy
    LIB_DIRS                        = [r'D:\WORKSPACE\0000_libraries\Plecs']                   # folders of your libraries ([] = none)
    VARS                            = None                                                   # ModelVars: dict, path of a JSON file, or None (values kept as in the model)
    CONTROLLER                      = 'MCU'                                                  # controller subsystem (stays outside the plant)
    OFFLINE                         = ('Scopes', 'Data Export')                              # blocks kept outside the plant, not in the generated code
    GATE_WIDTH                      = 6                                                      # width of the gate bus of the plant

    import json
    if isinstance(VARS, str):
        with open(VARS, encoding='utf-8') as f:
            VARS                    = json.load(f)
        VARS                        = VARS.get('ModelVars', VARS) if isinstance(VARS, dict) else {}
    RTBoxModel.write(MODEL, VARS, LIB_DIRS, controller=CONTROLLER, offline=OFFLINE, gate_width=GATE_WIDTH)
