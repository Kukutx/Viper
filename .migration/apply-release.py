from pathlib import Path
import re, hashlib
p=Path('.github/workflows/flutter-build.yml')
s=p.read_text()
assert hashlib.sha1(f'blob {len(p.read_bytes())}\0'.encode()+p.read_bytes()).hexdigest() == '9c6d86e4913d9e5976bc6432a8ab75dc15b9f283'
policy="inputs.upload-artifact && github.repository == 'Kukutx/Viper' && !startsWith(github.event_name, 'pull_request') && (github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/'))"
s=s.replace('  #signing keys env variable checks\n  ANDROID_SIGNING_KEY: "${{ secrets.ANDROID_SIGNING_KEY }}"\n  MACOS_P12_BASE64: "${{ secrets.MACOS_P12_BASE64 }}"\n  UPLOAD_ARTIFACT: "${{ inputs.upload-artifact }}"\n  SIGN_BASE_URL: "${{ secrets.SIGN_BASE_URL }}-2"',
'''  # Only availability booleans are shared; credentials are scoped to signing steps.
  RELEASE_ALLOWED: "${{ '''+policy+''' }}"
  HAS_ANDROID_SIGNING: "${{ secrets.ANDROID_SIGNING_KEY != '' }}"
  HAS_MACOS_SIGNING: "${{ secrets.MACOS_P12_BASE64 != '' }}"
  HAS_WINDOWS_SIGNING: "${{ secrets.SIGN_BASE_URL != '' && secrets.SIGN_SECRET_KEY != '' }}"
  UPLOAD_ARTIFACT: "${{ inputs.upload-artifact }}"''')
s=s.replace("env.ANDROID_SIGNING_KEY != null", "env.HAS_ANDROID_SIGNING == 'true'")
s=s.replace("env.ANDROID_SIGNING_KEY == null", "env.HAS_ANDROID_SIGNING != 'true'")
s=s.replace("env.MACOS_P12_BASE64 != null", "env.HAS_MACOS_SIGNING == 'true'")
s=s.replace("env.SIGN_BASE_URL != '-2'", "env.HAS_WINDOWS_SIGNING == 'true'")
parts=re.split(r'(?=^      - )',s,flags=re.M)
for i,block in enumerate(parts):
 if not block.startswith('      - '):continue
 active='\n'.join(l for l in block.splitlines() if not l.lstrip().startswith('#'))
 sensitive='secrets.' in active or 'env.HAS_' in active or 'softprops/action-gh-release@' in active
 if not sensitive: continue
 m=re.search(r'^        if: (.+)$',block,re.M)
 if not m:raise RuntimeError('Sensitive step has no condition: '+block[:160])
 old=m.group(1).strip()
 if old.startswith('${{'):old=old[3:-2].strip()
 block=block[:m.start()]+"        if: ${{ env.RELEASE_ALLOWED == 'true' && ("+old+") }}"+block[m.end():]
 if 'SECRET_KEY=${{ secrets.SIGN_SECRET_KEY }}' in block:
  block=block.replace('        run: |',"        env:\n          BASE_URL: ${{ format('{0}-2', secrets.SIGN_BASE_URL) }}\n          SECRET_KEY: ${{ secrets.SIGN_SECRET_KEY }}\n        run: |",1)
  block=block.replace('BASE_URL=${{ env.SIGN_BASE_URL }} SECRET_KEY=${{ secrets.SIGN_SECRET_KEY }} ','')
 if 'name: Import notarize key' in block:
  block=block.replace('fileDir: ${{ github.workspace }}','fileDir: ${{ runner.temp }}/viper-signing')
 if 'name: Codesign app and create signed dmg' in block:
  block=block.replace('        run: |',"        env:\n          MACOS_P12_PASSWORD: ${{ secrets.MACOS_P12_PASSWORD }}\n          MACOS_CODESIGN_IDENTITY: ${{ secrets.MACOS_CODESIGN_IDENTITY }}\n          NOTARIZE_KEY: ${{ runner.temp }}/viper-signing/rustdesk.json\n        run: |\n          identity=$(python tools/signing_identity.py)",1)
  block=block.replace('security unlock-keychain -p ${{ secrets.MACOS_P12_PASSWORD }}','security unlock-keychain -p "$MACOS_P12_PASSWORD"')
  block=block.replace('          # the identity secret carries its own shell quoting, so expand it inline like the dmg codesign below\n','')
  block=block.replace('            ${{ secrets.MACOS_CODESIGN_IDENTITY }} \\', '            "$identity" \\')
  block=block.replace('-s ${{ secrets.MACOS_CODESIGN_IDENTITY }}','-s "$identity"')
  block=block.replace('${{ github.workspace }}/rustdesk.json','"$NOTARIZE_KEY"')
  block+='''      - name: Remove temporary notarization credential
        if: ${{ always() && env.RELEASE_ALLOWED == 'true' && env.HAS_MACOS_SIGNING == 'true' }}
        env:
          NOTARIZE_KEY: ${{ runner.temp }}/viper-signing/rustdesk.json
        run: rm -f -- "$NOTARIZE_KEY"

'''
 parts[i]=block
s=''.join(parts)
parts=re.split(r'(?=^      - )',s,flags=re.M)
for i,block in enumerate(parts):
 if 'uses: actions/checkout@' not in block:continue
 if 'persist-credentials:' in block:continue
 if re.search(r'^        with:\s*$',block,re.M):block=re.sub(r'^(        with:\s*)$',r'\1\n          persist-credentials: false',block,count=1,flags=re.M)
 else:
  lines=block.splitlines(keepends=True)
  idx=next(j for j,l in enumerate(lines) if 'uses: actions/checkout@' in l)
  lines.insert(idx+1,'        with:\n          persist-credentials: false\n');block=''.join(lines)
 parts[i]=block
s=''.join(parts)
s=s.replace('        default: true\n','        default: false\n',1)
p.write_text(s)
assert hashlib.sha256(p.read_bytes()).hexdigest() == '1b1ea38c72aa41c67a5a30101658c215bfbbd122553d2ee368deb150eca62330'
