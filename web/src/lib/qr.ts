import QRCode from 'qrcode';

/** otpauth URL → data URL (PNG). 외부 서비스로 secret 누출 없이 브라우저 로컬에서 렌더. */
export async function otpauthToDataUrl(otpauth: string, size = 200): Promise<string> {
	return QRCode.toDataURL(otpauth, {
		width: size,
		margin: 1,
		errorCorrectionLevel: 'M',
	});
}
