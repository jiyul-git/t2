"""히어로 자동 진행 — 내가 쓰던 판단 기준을 그대로 옮긴 것.

핸드마다 손으로 치면 너무 느려서, 지금까지 내린 결정과 같은 원칙을
규칙으로 적었다. 봇 로직을 쓰는 게 아니라 히어로 자리의 내 정책이다.
"""
import sys, os, re
# 절대경로를 박으면 테스트 환경에 따라 **다른 복사본의 코드가 실행된다.**
# 이 파일 위치를 기준으로 프로젝트 루트를 잡는다.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.environ.setdefault('T2_LIVE_STATE', os.path.join(_ROOT, 'claude_state.json'))
import live2

R = '23456789TJQKA'
OPEN = {  # 포지션별 오픈 하한 (상위 %)
    'UTG': 0.13, 'UTG+1': 0.15, 'LJ': 0.18, 'HJ': 0.22,
    'CO': 0.28, 'BTN': 0.40, 'SB': 0.42, 'BB': 0.20,
}


def pct(hand):
    """대략적인 핸드 상위 %. 낮을수록 강함."""
    a, b = hand[0], hand[1]
    hi, lo = max(R.index(a[0]), R.index(b[0])), min(R.index(a[0]), R.index(b[0]))
    su = a[1] == b[1]
    if hi == lo:                                  # 페어
        return max(0.005, 0.06 - 0.004*(hi-0))
    gap = hi - lo
    base = 0.90 - 0.055*hi - 0.020*lo + 0.030*gap
    if su:
        base -= 0.09
    return max(0.02, min(1.0, base))


def parse(v):
    d = {}
    m = re.search(r'← 너\s+(\S+)\s+(\S+)', v)
    d['hand'] = None
    if m:
        conv = {'♠': 's', '♥': 'h', '♦': 'd', '♣': 'c'}
        d['hand'] = [c[0] + conv.get(c[1], 's') for c in (m.group(1), m.group(2))]
    m = re.search(r'← 너', v)
    line = [l for l in v.split('\n') if '← 너' in l]
    d['pos'] = line[0].split()[1] if line else 'BB'
    d['bb'] = 0.0
    m = re.search(r'\(([\d.]+)bb\)\s+← 너', v)
    if m:
        d['bb'] = float(m.group(1))
    d['board'] = '보드' in v
    d['tocall'] = 0.0
    m = re.search(r'콜 비용 [\d,]+ \(([\d.]+)bb\)', v)
    if m:
        d['tocall'] = float(m.group(1))
    d['pot'] = 0.0
    m = re.search(r'팟 [\d,]+ \(([\d.]+)bb\)', v)
    if m:
        d['pot'] = float(m.group(1))
    d['faced'] = ('레이즈' in v.split('현재')[-1]) or ('올인' in v.split('현재')[-1]) \
        if '현재' in v else False
    d['can_check'] = 'ㅊㅋ' in v
    return d


def decide(v):
    d = parse(v)
    if not d['hand']:
        return ('fold', 0)
    p = pct(d['hand'])
    st = d['bb']

    if not d['board']:                            # ---- 프리플랍 ----
        thr = OPEN.get(d['pos'], 0.25)
        if st <= 12:                              # 숏스택: 넓게 밀기
            if p <= thr*2.2:
                return ('raise', int(st*1000))
            return ('fold', 0)
        if d['tocall'] <= 0.01:                   # 아무도 안 침 → 오픈
            return ('raise', 2200) if p <= thr else ('fold', 0)
        if d['faced']:                            # 레이즈 대면
            if p <= 0.035:
                return ('raise', int(d['pot']*1000*2.6))
            if p <= thr*0.85 and d['tocall'] <= d['pot']*0.45:
                return ('call', 0)
            return ('fold', 0)
        if d['tocall'] <= 1.2 and p <= thr*1.6:   # 싼 디펜스
            return ('call', 0)
        return ('fold', 0)

    # ---- 포스트플랍: 보수적으로. 저항 없으면 소액, 저항 있으면 접는다 ----
    if d['can_check'] and d['tocall'] <= 0.01:
        return ('check', 0)
    if d['tocall'] <= d['pot']*0.30 and p <= 0.30:
        return ('call', 0)
    return ('fold', 0)


def main():
    n = 0
    while n < 400:
        r = live2.step()
        if r.get('done'):
            n += 1
            continue
        v = r['view']
        if '💀' in v or '🏆' in v:
            print(v[-400:])
            return
        a, amt = decide(v)
        try:
            r = live2.step(a, amt)
        except Exception:
            r = live2.step('fold')
        if r.get('done'):
            n += 1
        if '💀' in r.get('view', '') or '🏆' in r.get('view', ''):
            print(r['view'][-500:])
            return
    print('400핸드 도달 — 미종료')
    print(live2.step()['view'][:600])


if __name__ == '__main__':
    main()
