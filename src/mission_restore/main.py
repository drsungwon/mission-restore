# ==============================================================================
# Code Restore from Log Utility (v4.4 - Enhanced CLI Output)
# ------------------------------------------------------------------------------
# 이 스크립트는 단 하나의 '개발 과정 로그 파일'만으로 최종 버전의 소스 코드를
# 완벽하게 복원합니다. README.md에 명시된 전문적인 CLI 출력 형식을 적용하여
# 사용자 경험을 향상시켰습니다.
# ==============================================================================

import re
import sys
import os
import argparse

# --- CLI 출력 헬퍼 함수 ---
# 이 함수들은 스크립트의 모든 터미널 출력을 일관된 형식으로 만들어줍니다.
# 이를 통해 사용자에게 현재 진행 상황을 명확하고 전문적으로 전달할 수 있습니다.
def print_info(message: str): print(f"[  INFO   ] {message}")
def print_step(message: str): print(f"[ STEP {message}")
def print_ok(message: str): print(f"[   OK    ] {message}")
def print_progress(message: str): print(f"[   ...   ] {message}")
def print_success(message: str): print(f"[ SUCCESS ] {message}")
def print_error(message: str): print(f"[  ERROR  ] {message}")
def print_failed(message: str): print(f"[ FAILED  ] {message}")
# -------------------------

def parse_log_file(log_content: str) -> tuple[str, list[str]] | tuple[None, None]:
    """
    로그 파일의 전체 문자열 내용을 받아 '초기 코드'와 'diff 블록 리스트'를 분리합니다.

    이 함수는 정규식을 사용하여 두 가지 주요 정보를 추출하며, CLI 출력은 하지 않습니다.
    1.  '🦊=== Initial version of ... ==='로 시작하는 블록의 내용 (초기 코드)
    2.  '--- previous version'과 '+++ current version'으로 구분되는 모든 diff 블록

    Args:
        log_content (str): 읽어온 로그 파일의 전체 내용.

    Returns:
        성공 시:
            tuple[str, list[str]]: 첫 번째 요소는 초기 코드 문자열,
                                  두 번째 요소는 추출된 diff 블록들의 리스트.
        실패 시 (초기 버전 블록을 찾지 못한 경우):
            tuple[None, None]: 두 요소 모두 None을 반환하여 파싱 실패를 알립니다.
    """
    # 1. 초기 버전 코드 추출
    # re.DOTALL 플래그를 사용하여 '.'이 개행문자(\n)도 포함하도록 합니다.
    # `(?=\n🦊=== Code changes at|$)`는 비-캡처 긍정형 전방탐색(non-capturing positive lookahead)으로,
    # 다음에 'Code changes' 블록이 나오거나 파일의 끝이 나오기 직전까지를 매칭 범위로 한정합니다.
    initial_version_match = re.search(
        r"🦊=== Initial version of .*? ===\n(.*?)(?=\n🦊=== Code changes at|$)",
        log_content,
        re.DOTALL
    )
    
    # 초기 버전 블록 자체가 없는 치명적인 경우
    if not initial_version_match:
        # 헤더는 있지만 내용이 없는 경우를 대비해 헤더 존재 여부만으로 한 번 더 확인합니다.
        initial_version_header_match = re.search(r"🦊=== Initial version of .*? ===", log_content)
        if not initial_version_header_match:
            # 헤더조차 찾을 수 없으면, 복원을 진행할 수 없으므로 None을 반환합니다.
            return None, None
        # 헤더는 있으나 코드가 비어있는 경우, 빈 문자열로 처리합니다.
        initial_code = "" 
    else:
        initial_code_raw = initial_version_match.group(1)
        # ★★★ 핵심 안정성 로직 ★★★
        # 정규식 캡처 시, 헤더 바로 다음의 불필요한 개행 문자를 lstrip으로 제거합니다.
        # 이 개행이 남아있으면 전체 코드의 줄 번호(인덱스)가 1씩 밀려,
        # 이후 diff 적용 시 '컨텍스트 불일치' 오류를 유발하므로 반드시 제거해야 합니다.
        initial_code = initial_code_raw.lstrip('\n') if initial_code_raw is not None else ""

    # 2. 모든 diff 블록 추출
    # re.compile을 사용하여 정규식 패턴을 미리 컴파일해두면, 반복 사용 시 약간의 성능 향상이 있습니다.
    pattern = re.compile(
        r"--- previous version\s*\n\+\+\+ current version\s*\n(.*?)(?=\n🦊===|$)",
        re.DOTALL
    )
    # findall을 사용하여 매칭되는 모든 diff 내용을 리스트로 가져옵니다.
    diffs = pattern.findall(log_content)
    
    return initial_code, diffs

def apply_single_diff_robust(source_code: str, diff_content: str) -> str | None:
    """
    단일 diff 덩어리(patch)를 원본 소스 코드에 적용합니다.

    이 함수는 'patch' 유틸리티와 유사하게 동작하며, 특히 안정성에 중점을 둡니다.
    - 여러 개의 수정 묶음(hunk)을 처리할 수 있습니다.
    - 컨텍스트 라인(context line, ' '로 시작)을 원본과 비교하여 diff가 정확한 위치에
      적용되는지 검증합니다. 불일치 시, 복원을 중단하고 None을 반환합니다.

    Args:
        source_code (str): diff를 적용할 원본 코드.
        diff_content (str): 적용할 diff의 내용 (unified diff format).

    Returns:
        str | None: diff 적용이 성공한 경우, 수정된 전체 코드 문자열을 반환합니다.
                    실패(컨텍스트 불일치 등)한 경우, None을 반환합니다.
    """
    source_lines = source_code.split('\n')
    diff_lines = diff_content.split('\n')

    if not diff_lines:
        return source_code

    if not diff_lines[0].startswith("@@"):
        if all(line.startswith('+') or not line.strip() for line in diff_lines):
            code_to_add = [line[1:] for line in diff_lines if line.startswith('+')]
            return "\n".join(source_lines + code_to_add)
        else:
            print_error(f"알 수 없는 diff 형식입니다 (헤더 없음): {diff_lines[0]}")
            return None

    result_lines = []
    last_source_line_processed = 0

    hunk_indices = [i for i, line in enumerate(diff_lines) if line.startswith("@@")]
    
    for i, start_index in enumerate(hunk_indices):
        hunk_header = diff_lines[start_index]
        end_index = hunk_indices[i + 1] if i + 1 < len(hunk_indices) else len(diff_lines)
        hunk_body = diff_lines[start_index + 1:end_index]
        
        match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*)", hunk_header.strip())
        if not match:
            print_error(f"diff 헤더를 파싱할 수 없습니다: {hunk_header}")
            return None
        
        try:
            old_start = int(match.group(1))
        except (ValueError, IndexError) as e:
            print_error(f"diff 헤더 숫자 변환 중 오류 발생: {e} | 헤더: {hunk_header}")
            return None

        if old_start > 0 and old_start - 1 > last_source_line_processed:
             result_lines.extend(source_lines[last_source_line_processed:old_start - 1])
        
        source_pointer = old_start - 1 if old_start > 0 else 0
        
        for line in hunk_body:
            if not line: continue
            
            op, line_content = line[0], line[1:]
            
            if op == ' ':
                if source_pointer >= len(source_lines) or source_lines[source_pointer] != line_content:
                    print_error("치명적 오류: 컨텍스트 불일치 발생!")
                    print(f"             - 예상된 소스({source_pointer+1}): '{line_content}'")
                    print(f"             - 실제 소스({source_pointer+1}): '{source_lines[source_pointer] if source_pointer < len(source_lines) else 'EOF'}'")
                    return None
                result_lines.append(line_content)
                source_pointer += 1
            elif op == '+':
                result_lines.append(line_content)
            elif op == '-':
                if source_pointer >= len(source_lines) or source_lines[source_pointer] != line_content:
                    print_error("치명적 오류: 삭제할 라인 불일치 발생!")
                    print(f"             - 예상된 소스({source_pointer+1}): '{line_content}'")
                    print(f"             - 실제 소스({source_pointer+1}): '{source_lines[source_pointer] if source_pointer < len(source_lines) else 'EOF'}'")
                    return None
                source_pointer += 1
            else:
                print(f"[ WARNING ] 알 수 없는 diff 라인 형식 (무시): {line}")

        last_source_line_processed = source_pointer

    if last_source_line_processed < len(source_lines):
        result_lines.extend(source_lines[last_source_line_processed:])
    
    return "\n".join(result_lines)


def apply_all_diffs(initial_code: str, diffs: list[str]) -> str | None:
    """
    초기 코드에 모든 diff들을 순차적으로 적용합니다.

    이 함수는 각 diff 적용 시 진행 상황을 CLI에 출력합니다.
    Args:
        initial_code (str): 복원의 기준이 될 초기 코드.
        diffs (list[str]): 순서대로 적용할 diff들의 리스트.

    Returns:
        str | None: 모든 diff가 성공적으로 적용된 최종 코드.
                    중간에 하나라도 실패하면 None을 반환합니다.
    """
    current_code = initial_code
    for i, diff_text in enumerate(diffs, 1):
        next_code_version = apply_single_diff_robust(current_code, diff_text)
        
        if next_code_version is None:
             print_error(f"패치 #{i}를 적용하는 데 실패했습니다. 복원을 중단합니다.")
             return None
        
        current_code = next_code_version
        print_progress(f"패치 #{i} 적용 완료.")
        
    return current_code

def restore_code_from_log(log_file_path: str, output_file_path: str) -> None:
    """
    스크립트의 메인 로직을 수행하는 최상위 함수.
    전체 복원 과정을 조율하고 모든 사용자 대상 CLI 출력을 관리합니다.
    """
    # --- 시작 정보 출력 ---
    print_info(f"코드 복원 프로세스 (v4.4)를 시작합니다...")
    # 사용자에게 작업 대상 파일 경로를 명확히 보여주기 위해 절대 경로를 사용합니다.
    print(f"             - 입력 파일: {os.path.abspath(log_file_path)}")
    print(f"             - 출력 파일: {os.path.abspath(output_file_path)}\n")

    # --- 파일 유효성 검사 ---
    if not os.path.exists(log_file_path):
        print_error(f"로그 파일('{log_file_path}')을 찾을 수 없습니다.")
        return

    # --- STEP 1: 파일 읽기 및 파싱 ---
    print_step("1  ] 로그 파일에서 초기 코드와 변경 기록을 파싱합니다...")
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            # [최종 안정성 수정]
            # 모든 종류의 줄바꿈(CRLF, LF)을 표준 LF(\n)으로 통일합니다.
            # 이것으로 모든 후속 처리(split, join)에서 발생하는 혼란을 원천 차단합니다.
            log_content = f.read().replace('\r\n', '\n')
    except Exception as e:
        print_error(f"로그 파일을 읽는 중 문제가 발생했습니다: {e}")
        return
        
    initial_code_content, diff_list = parse_log_file(log_content)

    # 파싱 결과 유효성 검사. (None, None)을 반환했다면 복원을 진행할 수 없습니다.
    # 이 '타입 가드'를 통해 이 블록 아래에서는 두 변수가 None이 아님이 보장됩니다.
    if initial_code_content is None or diff_list is None:
        print_error("'Initial version' 블록을 찾지 못해 파싱에 실패했습니다.")
        print_failed(f"'{os.path.basename(log_file_path)}' 처리 중단.")
        return
    
    print_ok("초기 버전 코드를 성공적으로 추출했습니다.")
    print_ok(f"총 {len(diff_list)}개의 변경 기록(diff)을 찾았습니다.")

    # --- STEP 2: Diff 적용 ---
    print_step("2  ] 초기 코드에 변경 기록을 순차적으로 적용합니다...")
    final_code = apply_all_diffs(initial_code_content, diff_list)

    # Diff 적용 중 하나라도 실패하면(None 반환) 프로세스를 중단합니다.
    if final_code is None:
        print_failed(f"'{os.path.basename(log_file_path)}' 처리 중 치명적 오류 발생.")
        return

    # --- STEP 3: 결과 저장 ---
    print_step(f"3  ] '{output_file_path}' 파일에 결과를 저장합니다...")
    output_dir = os.path.dirname(output_file_path)
    # 출력 경로의 디렉터리가 존재하지 않는 경우, 안전하게 생성합니다.
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            print_error(f"출력 디렉터리를 생성할 수 없습니다: {e}")
            print_failed(f"'{os.path.basename(log_file_path)}' 처리 중단.")
            return
            
    try:
        # [최종 출력 표준화]
        standardized_final_code = final_code.rstrip() + '\n'

        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(standardized_final_code)
        print_success(f"최종 복원된 코드를 '{os.path.abspath(output_file_path)}' 파일로 저장했습니다.")
    except IOError as e:
        print_error(f"최종 코드를 파일에 쓰는 중 문제가 발생했습니다: {e}")
        print_failed(f"'{os.path.basename(log_file_path)}' 처리 중단.")

if __name__ == "__main__":
    # --- 명령줄 인자 파서 설정 ---
    # argparse를 사용하여 사용자 친화적인 CLI를 구현합니다.
    parser = argparse.ArgumentParser(
        description="개발 과정 로그 파일로부터 최종 소스 코드를 복원합니다.",
        formatter_class=argparse.RawTextHelpFormatter # 도움말 메시지의 줄바꿈을 유지합니다.
    )
    # 필수 위치 인자(Positional Argument) 2개를 정의합니다.
    parser.add_argument('log_file', help='복원할 개발 과정 로그 파일의 경로입니다.')
    parser.add_argument('output_file', help='최종 복원된 코드를 저장할 파일의 경로입니다.')

    # sys.argv로부터 인자를 파싱합니다. 잘못된 인자가 들어오면 자동으로 도움말을 보여주고 종료됩니다.
    args = parser.parse_args()
    
    # 파싱된 인자를 사용하여 메인 복원 함수를 호출합니다.
    restore_code_from_log(args.log_file, args.output_file)