import {defineConfig} from 'vite';
export default defineConfig({server:{host:'127.0.0.1',proxy:{'/api':'http://127.0.0.1:8765'}},build:{target:'es2022',rollupOptions:{treeshake:false}}});
