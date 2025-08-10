const { IExecuteFunctions, NodeOperationError } = require('n8n-workflow');
const axios = require('axios');
const FormData = require('form-data');
const stream = require('stream');

module.exports = {
	name: 'typhoonOcr',
	displayName: 'Typhoon OCR',
	description: 'Process documents using Typhoon OCR with pre-processing and layout analysis options',
	version: 1,
	defaults: {
		name: 'Typhoon OCR',
	},
	inputs: ['main'],
	outputs: ['main'],
	credentials: [
		{
			name: 'typhoonOcrApi',
			required: true,
		},
	],
	properties: [
		// ... existing operation property ...
		{
			displayName: 'Operation',
			name: 'operation',
			type: 'options',
			noDataExpression: true,
			options: [
				{
					name: 'Process Document',
					value: 'processDocument',
					description: 'Process a document using OCR',
				},
			],
			default: 'processDocument',
		},
		// --- File to Process ---
		{
			displayName: 'Source File',
			name: 'sourceFile',
			type: 'string',
			default: '',
			required: true,
			description: 'The file to process. Can be from a previous node (using an expression) or a URL.',
			placeholder: '={{ $binary.data }} or https://example.com/file.pdf',
		},
		// --- Processing Options ---
		{
			displayName: 'Page Number',
			name: 'pageNumber',
			type: 'number',
			typeOptions: {
				minValue: 1,
			},
			default: 1,
			description: 'The page number of the PDF to process',
		},
		{
			displayName: 'Use Unstructured',
			name: 'useUnstructured',
			type: 'boolean',
			default: false,
			description:
				'Whether to use Unstructured.io for layout-aware text extraction. This provides better structure (e.g., tables, titles) but may be slower.',
		},
		{
			displayName: 'Task Type (for Standard OCR)',
			name: 'taskType',
			type: 'options',
			displayOptions: {
				show: {
					useUnstructured: [false], // Only show when not using Unstructured
				},
			},
			options: [
				{
					name: 'Default',
					value: 'default',
				},
				{
					name: 'Structure',
					value: 'structure',
				},
			],
			default: 'default',
			description: 'The type of standard OCR processing to perform.',
		},
		{
			displayName: 'Perform Text Cleanup',
			name: 'performCleanup',
			type: 'boolean',
			default: true,
			description: 'Whether to automatically clean the OCR output by removing page markers and normalizing whitespace.',
		},
	],
	async execute() {
		const items = this.getInputData();
		const returnData = [];

		for (let i = 0; i < items.length; i++) {
			try {
				const sourceFile = this.getNodeParameter('sourceFile', i);
				const pageNumber = this.getNodeParameter('pageNumber', i);
				const useUnstructured = this.getNodeParameter('useUnstructured', i);
				const taskType = this.getNodeParameter('taskType', i);
				const performCleanup = this.getNodeParameter('performCleanup', i);

				const form = new FormData();
				form.append('page_num', pageNumber);
				form.append('use_unstructured', useUnstructured);
				form.append('task_type', taskType);
				form.append('perform_cleanup', performCleanup);

				let fileBuffer;
				let fileName;

				// Check if the sourceFile is a URL or binary data from a previous node
				if (sourceFile.startsWith('http')) {
					const response = await axios.get(sourceFile, { responseType: 'arraybuffer' });
					fileBuffer = response.data;
					fileName = sourceFile.split('/').pop();
				} else {
					// Assume it's binary data from a previous node
					const binaryData = this.helpers.getBinaryDataBuffer(i, 'sourceFile');
					fileBuffer = binaryData;
					// How to get the filename from binary data is tricky in n8n,
					// let's default to a generic name. The extension is what matters.
					const binaryInfo = this.helpers.getBinaryInfo(i, 'sourceFile');
					fileName = binaryInfo.fileName || 'file.pdf';
				}

				const fileStream = new stream.Readable();
				fileStream._read = () => {}; // _read is required
				fileStream.push(fileBuffer);
				fileStream.push(null);

				form.append('file', fileStream, { filename: fileName });

				const response = await axios.post(`${process.env.TYPHOON_OCR_URL}/process`, form, {
					headers: {
						...form.getHeaders(),
						'Authorization': `Bearer ${process.env.TYPHOON_OCR_API_KEY}`,
					},
					maxContentLength: Infinity,
			maxBodyLength: Infinity,
				});

				returnData.push({
					json: response.data,
					// Paired item is necessary for n8n's data structure
					pairedItem: { item: i },
				});

			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: error.message },
						pairedItem: { item: i },
					});
					continue;
				}
				throw new NodeOperationError(this.getNode(), error, { itemIndex: i });
			}
		}

		return [this.helpers.returnJsonArray(returnData)];
	},
};
