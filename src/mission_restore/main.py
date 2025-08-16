# ==============================================================================
# Code Restore from Log Utility (v4.3 - UX Improved)
# ------------------------------------------------------------------------------
# 이 스크립트는 단 하나의 '개발 과정 로그 파일'만으로 최종 버전의 소스 코드를
# 완벽하게 복원합니다. 초기 코드 파싱 시 발생하는 줄 번호 밀림 현상을
# 수정하여 모든 케이스에 대한 완벽한 복원을 보장하며, argparse를 사용하여
# 명확한 CLI 인터페이스를 제공합니다.
# ==============================================================================

import re
import sys
import os
import argparse  # CLI 인자 처리를 위해 argparse 모듈을 임포트합니다.

def parse_log_file(log_content: str) -> tuple[str, list[str]] | tuple[None, None]:
    """
    로그 파일의 전체 문자열 내용을 받아 '초기 코드'와 'diff 블록 리스트'를 분리합니다.

    이 함수는 정규식을 사용하여 두 가지 주요 정보를 추출합니다.
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
            print("  오류: 로그 파일에서 'Initial version' 블록을 찾을 수 없습니다.")
            return None, None
        # 헤더는 있으나 코드가 비어있는 경우, 빈 문자열로 처리합니다.
        initial_code = "" 
    else:
        initial_code_raw = initial_version_match.group(1)
        # ★★★★★★★★★★★★★★★★★★★★★ 최종 수정 부분 ★★★★★★★★★★★★★★★★★★★★★
        # 정규식 캡처 시, 헤더 바로 다음의 불필요한 개행 문자가 포함될 수 있습니다.
        # 이 개행 문자를 제거하지 않으면 코드 전체의 줄 번호(인덱스)가 1씩 밀려,
        # 이후 diff 적용 시 '컨텍스트 불일치' 오류를 유발합니다.
        # .strip()이나 .rstrip()은 코드 끝의 중요한 공백/개행을 제거할 위험이 있으므로,
        # 코드 시작 부분의 개행만 안전하게 제거하는 .lstrip('\n')을 사용합니다.
        initial_code = initial_code_raw.lstrip('\n') if initial_code_raw is not None else ""
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    print("  - 초기 버전 코드를 성공적으로 추출했습니다.")

    # 2. 모든 diff 블록 추출
    # re.compile을 사용하여 정규식 패턴을 미리 컴파일해두면, 반복 사용 시 약간의 성능 향상이 있습니다.
    pattern = re.compile(
        r"--- previous version\s*\n\+\+\+ current version\s*\n(.*?)(?=\n🦊===|$)",
        re.DOTALL
    )
    # findall을 사용하여 매칭되는 모든 diff 내용을 리스트로 가져옵니다.
    diffs = pattern.findall(log_content)
    print(f"  - 총 {len(diffs)}개의 변경 기록(diff)을 찾았습니다.")
    
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
    # 소스 코드와 diff 내용을 줄 단위로 분리하여 처리의 기본 단위로 삼습니다.
    source_lines = source_code.splitlines()
    diff_lines = diff_content.splitlines()

    # diff 내용이 비어있으면 원본 코드를 그대로 반환합니다.
    if not diff_lines:
        return source_code

    # 특수 케이스 처리: diff에 hunk 헤더('@@ ... @@')가 없고, 전체가 추가(+) 라인으로만
    # 구성된 경우, 이는 파일 끝에 내용을 추가하는 것으로 간주합니다.
    if not diff_lines[0].startswith("@@"):
        if all(line.startswith('+') or not line.strip() for line in diff_lines):
            code_to_add = [line[1:] for line in diff_lines if line.startswith('+')]
            return "\n".join(source_lines + code_to_add)
        else:
            print(f"오류: 알 수 없는 diff 형식입니다 (헤더 없음): {diff_lines[0]}")
            return None

    # 최종 결과 코드를 저장할 리스트
    result_lines = []
    # 원본 소스 코드에서 마지막으로 처리된 줄 번호를 추적합니다.
    # 이는 여러 hunk 사이의 미수정된 코드 부분을 그대로 복사하기 위해 사용됩니다.
    last_source_line_processed = 0

    # diff 내용에서 모든 hunk 헤더('@@')의 인덱스를 찾아, 여러 hunk를 순차적으로 처리합니다.
    hunk_indices = [i for i, line in enumerate(diff_lines) if line.startswith("@@")]
    
    for i, start_index in enumerate(hunk_indices):
        hunk_header = diff_lines[start_index]
        # 현재 hunk의 끝 인덱스를 결정합니다. 다음 hunk의 시작점이거나, 마지막 hunk인 경우 diff의 끝입니다.
        end_index = hunk_indices[i + 1] if i + 1 < len(hunk_indices) else len(diff_lines)
        hunk_body = diff_lines[start_index + 1:end_index]
        
        # Hunk 헤더 파싱 (예: "@@ -1,5 +1,6 @@")
        match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*)", hunk_header.strip())
        if not match:
            print(f"오류: diff 헤더를 파싱할 수 없습니다: {hunk_header}")
            return None
        
        try:
            # 이전 버전(-)의 시작 줄 번호를 추출합니다. 이 번호는 1-based index입니다.
            old_start = int(match.group(1))
        except (ValueError, IndexError) as e:
            print(f"오류: diff 헤더 숫자 변환 중 오류 발생: {e} | 헤더: {hunk_header}")
            return None

        # 이전 hunk와 현재 hunk 사이의 변경되지 않은 코드 라인들을 결과에 추가합니다.
        # old_start-1 은 0-based index로 변환한 것입니다.
        if old_start > 0 and old_start - 1 > last_source_line_processed:
             result_lines.extend(source_lines[last_source_line_processed:old_start - 1])
        
        # 원본 소스 코드에서 현재 처리 위치를 가리키는 포인터입니다 (0-based).
        source_pointer = old_start - 1 if old_start > 0 else 0
        
        # Hunk 본문을 한 줄씩 처리합니다.
        for line in hunk_body:
            if not line: continue  # 빈 줄은 건너뜁니다.
            
            op, line_content = line[0], line[1:]
            
            # 컨텍스트 라인 (' '): 변경되지 않은 줄. 원본 코드와 일치하는지 *반드시* 검증해야 합니다.
            if op == ' ':
                if source_pointer >= len(source_lines) or source_lines[source_pointer] != line_content:
                    print(f"치명적 오류: 컨텍스트 불일치 발생!")
                    print(f"  - 예상된 소스({source_pointer+1}): '{line_content}'")
                    print(f"  - 실제 소스({source_pointer+1}): '{source_lines[source_pointer] if source_pointer < len(source_lines) else 'EOF'}'")
                    return None
                result_lines.append(line_content)
                source_pointer += 1 # 원본 포인터를 다음 줄로 이동
            # 추가 라인 ('+'): 결과에 새로운 줄을 추가합니다.
            elif op == '+':
                result_lines.append(line_content)
            # 삭제 라인 ('-'): 원본 코드와 일치하는지 검증 후, 결과에는 추가하지 않고 원본 포인터만 이동시킵니다.
            elif op == '-':
                if source_pointer >= len(source_lines) or source_lines[source_pointer] != line_content:
                    print(f"치명적 오류: 삭제할 라인 불일치 발생!")
                    print(f"  - 예상된 소스({source_pointer+1}): '{line_content}'")
                    print(f"  - 실제 소스({source_pointer+1}): '{source_lines[source_pointer] if source_pointer < len(source_lines) else 'EOF'}'")
                    return None
                source_pointer += 1 # 원본 포인터를 다음 줄로 이동
            else: # '\ No newline at end of file' 등의 특수 라인은 현재 처리하지 않음
                print(f"경고: 알 수 없는 diff 라인 형식 (무시): {line}")
                
        # 현재 hunk 처리가 끝난 후, 원본 소스에서 마지막으로 처리된 줄 번호를 업데이트합니다.
        last_source_line_processed = source_pointer

    # 마지막 hunk 처리 후, 원본 파일의 남은 부분을 결과에 추가합니다.
    if last_source_line_processed < len(source_lines):
        result_lines.extend(source_lines[last_source_line_processed:])
    
    # 줄 리스트를 다시 하나의 문자열로 합쳐 반환합니다.
    return "\n".join(result_lines)


def apply_all_diffs(initial_code: str, diffs: list[str]) -> str | None:
    """
    초기 코드에 모든 diff들을 순차적으로 적용합니다.

    Args:
        initial_code (str): 복원의 기준이 될 초기 코드.
        diffs (list[str]): 순서대로 적용할 diff들의 리스트.

    Returns:
        str | None: 모든 diff가 성공적으로 적용된 최종 코드.
                    중간에 하나라도 실패하면 None을 반환합니다.
    """
    current_code = initial_code
    # enumerate를 사용하여 diff의 순번(패치 번호)을 함께 출력합니다.
    for i, diff_text in enumerate(diffs, 1):
        # apply_single_diff_robust를 호출하여 현재 코드 버전에 diff를 적용합니다.
        next_code_version = apply_single_diff_robust(current_code, diff_text)
        
        # 만약 diff 적용이 실패(None 반환)하면, 즉시 전체 프로세스를 중단합니다.
        if next_code_version is None:
             print(f"치명적 오류: 패치 #{i}를 적용하는 데 실패했습니다. 복원을 중단합니다.")
             return None
        
        # 성공 시, 다음 diff 적용을 위해 현재 코드를 업데이트합니다.
        current_code = next_code_version
        print(f"    - 패치 #{i} 적용 완료.")
        
    return current_code

def main(log_file_path: str, output_file_path: str) -> None:
    """
    스크립트의 메인 로직을 수행하는 함수입니다.

    파일 읽기, 파싱, diff 적용, 파일 저장의 전 과정을 조율합니다.

    Args:
        log_file_path (str): 입력으로 사용할 로그 파일의 경로.
        output_file_path (str): 복원된 코드를 저장할 파일의 경로.
    """
    print(f"코드 복원 프로세스 (v4.3 - UX Improved)를 시작합니다...\n")
    print(f"--- 작업 시작: '{os.path.basename(log_file_path)}' 처리 중 ---")

    # 1. 입력 파일 유효성 검사
    if not os.path.exists(log_file_path):
        print(f"  오류: 로그 파일('{log_file_path}')을 찾을 수 없습니다.")
        return

    # 2. 로그 파일 읽기
    print("  1. 로그 파일에서 초기 코드와 변경 기록을 파싱합니다.")
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
    except Exception as e:
        print(f"  오류: 로그 파일을 읽는 중 문제가 발생했습니다: {e}")
        return
        
    # 3. 로그 내용 파싱
    initial_code_content, diff_list = parse_log_file(log_content)

    # 4. 파싱 결과 유효성 검사 (타입 가드)
    # parse_log_file이 (None, None)을 반환한 경우, 프로세스를 중단합니다.
    # 이 검사를 통해 아래 코드 블록에서는 initial_code_content가 str, diff_list가 list[str]임을
    # 정적 분석기(Pylance 등)가 확신할 수 있게 되어 타입 안정성이 향상됩니다.
    if initial_code_content is None or diff_list is None:
        print(f"--- 작업 실패: '{os.path.basename(log_file_path)}' 파싱 중 오류 발생 ---\n")
        return

    # 5. Diff 적용
    print("  2. 초기 코드에 변경 기록을 순차적으로 적용합니다.")
    final_code = apply_all_diffs(initial_code_content, diff_list)

    # 6. 결과 저장
    if final_code is not None:
        # 출력 경로의 디렉터리가 존재하지 않으면 생성합니다.
        output_dir = os.path.dirname(output_file_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                print(f"  오류: 출력 디렉터리를 생성할 수 없습니다: {e}")
                return
            
        print(f"  3. 최종 복원된 코드를 '{output_file_path}' 파일로 저장합니다.")
        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(final_code)
            print(f"--- 작업 완료: '{output_file_path}' 생성 완료 ---\n")
        except IOError as e:
            print(f"  오류: 최종 코드를 파일에 쓰는 중 문제가 발생했습니다: {e}")
            print(f"--- 작업 실패: '{os.path.basename(log_file_path)}' 처리 중 오류 발생 ---\n")
    else:
        # apply_all_diffs가 None을 반환한 경우 (치명적 오류 발생 시)
        print(f"--- 작업 실패: '{os.path.basename(log_file_path)}' 처리 중 오류 발생 ---\n")

# 이 스크립트가 직접 실행될 때만 아래 코드가 동작합니다.
if __name__ == "__main__":
    # 1. ArgumentParser 객체 생성
    # description: -h 또는 --help 옵션 사용 시 프로그램에 대한 설명을 보여줍니다.
    parser = argparse.ArgumentParser(
        description="개발 과정 로그 파일로부터 최종 소스 코드를 복원합니다."
    )

    # 2. 위치 기반 인자(Positional Arguments) 추가
    # 스크립트 실행 시 반드시 제공해야 하는 인자들입니다.
    parser.add_argument(
        'log_file',  # 인자의 이름
        type=str,      # 인자의 타입 (기본값이지만 명시)
        help='복원할 개발 과정 로그 파일의 경로입니다.'  # 도움말 메시지
    )
    parser.add_argument(
        'output_file',
        type=str,
        help='최종 복원된 코드를 저장할 파일의 경로입니다.'
    )

    # 3. 명령줄 인자 파싱
    # sys.argv에서 인자들을 가져와 파싱하고, 정의된 규칙에 맞지 않으면 오류와 도움말을 출력합니다.
    try:
        args = parser.parse_args()
        # 4. 파싱된 인자를 main 함수에 전달하여 실행
        main(args.log_file, args.output_file)
    except SystemExit:
        # argparse가 인자 오류로 종료할 때 추가적인 메시지 없이 깔끔하게 종료되도록 합니다.
        pass