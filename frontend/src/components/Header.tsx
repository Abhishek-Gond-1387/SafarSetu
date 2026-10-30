import React from 'react';
import { Sidebar, SidebarProps } from './Sidebar';

export type HeaderProps = SidebarProps;

export const Header: React.FC<HeaderProps> = (props) => {
  return <Sidebar {...props} />;
};

export default Header;
