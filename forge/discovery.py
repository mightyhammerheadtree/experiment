"""Bounded recursive code discovery using iced-x86, not a custom CPU decoder.

This is an analysis hint, never proof that all reachable code has been found.
"""
from collections import deque
from pathlib import Path
import iced_x86 as ix
import pefile


def discover(path, budget=100000):
    if not 1 <= budget <= 1000000:
        raise ValueError('Instruction budget must be between 1 and 1000000')
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXCEPTION'], pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
    try:
        bits = {0x8664: 64, 0x14c: 32}.get(pe.FILE_HEADER.Machine)
        if bits is None:
            raise ValueError('Code discovery supports x64 and x86 only')
        base = pe.OPTIONAL_HEADER.ImageBase
        regions = []
        for s in pe.sections:
            if s.Characteristics & 0x20000000:
                regions.append((base+s.VirtualAddress, s.get_data()))
        def locate(va):
            for start, data in regions:
                if start <= va < start+len(data):
                    return start, data
            return None
        seeds = {base+pe.OPTIONAL_HEADER.AddressOfEntryPoint}
        unwind = getattr(pe, 'DIRECTORY_ENTRY_EXCEPTION', [])
        for entry in unwind:
            if hasattr(entry.struct, 'BeginAddress'):
                seeds.add(base+entry.struct.BeginAddress)
        exports = getattr(pe, 'DIRECTORY_ENTRY_EXPORT', None)
        if exports:
            seeds.update(base+s.address for s in exports.symbols if not s.forwarder)
        entry = base+pe.OPTIONAL_HEADER.AddressOfEntryPoint
        queue = deque([entry] + sorted(seeds - {entry}))
        visited = set()
        blocks = []
        indirect = []
        invalid = []
        calls = set()
        flow_names = {getattr(ix.FlowControl, k): k.lower() for k in dir(ix.FlowControl) if k.isupper()}
        sample = []
        formatter = ix.Formatter(ix.FormatterSyntax.INTEL)
        while queue and len(visited) < budget:
            pc = queue.popleft()
            if pc in visited or not locate(pc):
                continue
            start, data = locate(pc)
            decoder = ix.Decoder(bits, data[pc-start:], ip=pc)
            block_start = pc
            count = 0
            end = pc
            edges = []
            while decoder.can_decode and len(visited) < budget:
                inst = decoder.decode()
                if inst.ip in visited:
                    edges.append(inst.ip)
                    break
                visited.add(inst.ip)
                count += 1
                end = inst.next_ip
                if inst.is_invalid:
                    invalid.append(hex(inst.ip))
                    break
                if len(sample) < 80:
                    sample.append({'address': hex(inst.ip), 'text': formatter.format(inst)})
                flow = inst.flow_control
                if flow in (ix.FlowControl.UNCONDITIONAL_BRANCH, ix.FlowControl.CONDITIONAL_BRANCH, ix.FlowControl.CALL):
                    target = inst.near_branch_target
                    if locate(target):
                        queue.append(target)
                        edges.append(target)
                    if flow == ix.FlowControl.CALL:
                        calls.add(target)
                    if flow == ix.FlowControl.CONDITIONAL_BRANCH:
                        queue.append(inst.next_ip)
                        edges.append(inst.next_ip)
                    if flow != ix.FlowControl.CALL:
                        break
                elif flow in (ix.FlowControl.INDIRECT_BRANCH, ix.FlowControl.INDIRECT_CALL):
                    indirect.append({'address': hex(inst.ip), 'type': flow_names[flow]})
                    if flow == ix.FlowControl.INDIRECT_BRANCH:
                        break
                elif flow in (ix.FlowControl.RETURN, ix.FlowControl.INTERRUPT, ix.FlowControl.EXCEPTION):
                    break
            blocks.append({'start': hex(block_start), 'end': hex(end), 'instructions': count, 'edges': [hex(e) for e in edges]})
        return dict(decoder='iced-x86 1.21.0', bits=bits, image_base=hex(base), seeds=len(seeds), unwind_entries=len(unwind), instructions=len(visited), blocks=len(blocks), direct_call_targets=len(calls), indirect_count=len(indirect), indirect_sites=indirect[:200], invalid_count=len(invalid), invalid_sites=invalid[:200], budget=budget, budget_exhausted=bool(queue) and len(visited) >= budget, sample=sample, graph=blocks[:2000], limitations=['Heuristic discovery only; indirect calls, jump tables, packed code and runtime-generated code are not resolved.', 'Overlapping instruction streams and embedded data can produce misleading candidates.', 'An instruction budget bounds analysis; use GEX recording and strict-AOT validation for actual coverage.'])
    finally:
        pe.close()
